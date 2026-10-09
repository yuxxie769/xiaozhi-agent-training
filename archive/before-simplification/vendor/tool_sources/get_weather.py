import json

import requests
from bs4 import BeautifulSoup
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

GET_WEATHER_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": (
            "只在用户询问当前或未来七天的天气时调用；普通闲聊中提到天气时不要调用。"
            "用户明确说出城市时，将城市名填入location；同时明确说出省份或上级城市时，填入adm用于消歧，不要自行猜测上级地区。"
            "地点是省份、含糊地名或无法确定具体城市时先反问。用户没说地点时省略location，工具会使用当前智能体天气配置中的default_location；不要把上下文城市填入location。"
            "用户没说日期时按今天理解。工具返回当前天气和未来七天预报，不接收日期参数；只根据报告中确实存在的日期回答。回复时原样写出报告第一行的城市名，不要翻译或改写。"
            "若返回need_city、ambiguous_city或city_not_found，向用户追问具体城市或上级地区，再根据下一轮回答重新调用本工具；若返回fetch_error，说明暂时无法查询，不要编造天气。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "用户明确提出的城市名，如杭州、朝阳。未说城市时不要传此参数，由工具使用当前智能体配置的默认城市。",
                },
                "adm": {
                    "type": "string",
                    "description": "用户明确提供的上级省份或城市，仅用于重名地区消歧，例如辽宁；不要猜测。",
                },
                "lang": {
                    "type": "string",
                    "description": "返回用户使用的语言code，例如zh_CN/zh_HK/en_US/ja_JP等，默认zh_CN",
                },
            },
            "required": ["lang"],
        },
    },
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"
    )
}

# 天气代码 https://dev.qweather.com/docs/resource/icons/#weather-icons
WEATHER_CODE_MAP = {
    "100": "晴",
    "101": "多云",
    "102": "少云",
    "103": "晴间多云",
    "104": "阴",
    "150": "晴",
    "151": "多云",
    "152": "少云",
    "153": "晴间多云",
    "300": "阵雨",
    "301": "强阵雨",
    "302": "雷阵雨",
    "303": "强雷阵雨",
    "304": "雷阵雨伴有冰雹",
    "305": "小雨",
    "306": "中雨",
    "307": "大雨",
    "308": "极端降雨",
    "309": "毛毛雨/细雨",
    "310": "暴雨",
    "311": "大暴雨",
    "312": "特大暴雨",
    "313": "冻雨",
    "314": "小到中雨",
    "315": "中到大雨",
    "316": "大到暴雨",
    "317": "暴雨到大暴雨",
    "318": "大暴雨到特大暴雨",
    "350": "阵雨",
    "351": "强阵雨",
    "399": "雨",
    "400": "小雪",
    "401": "中雪",
    "402": "大雪",
    "403": "暴雪",
    "404": "雨夹雪",
    "405": "雨雪天气",
    "406": "阵雨夹雪",
    "407": "阵雪",
    "408": "小到中雪",
    "409": "中到大雪",
    "410": "大到暴雪",
    "456": "阵雨夹雪",
    "457": "阵雪",
    "499": "雪",
    "500": "薄雾",
    "501": "雾",
    "502": "霾",
    "503": "扬沙",
    "504": "浮尘",
    "507": "沙尘暴",
    "508": "强沙尘暴",
    "509": "浓雾",
    "510": "强浓雾",
    "511": "中度霾",
    "512": "重度霾",
    "513": "严重霾",
    "514": "大雾",
    "515": "特强浓雾",
    "900": "热",
    "901": "冷",
    "999": "未知",
}


def fetch_city_info(location, api_key, api_host, adm=None):
    params = {"key": api_key, "location": location, "lang": "zh", "number": 20}
    if adm:
        params["adm"] = adm
    http_response = requests.get(
        f"https://{api_host}/geo/v2/city/lookup",
        headers=HEADERS,
        params=params,
        timeout=10,
    )
    response = http_response.json()
    error = response.get("error")
    if isinstance(error, dict) and str(error.get("type", "")).endswith(
        "#no-such-location"
    ):
        return []
    if response.get("error") is not None or response.get("code", "200") != "200":
        logger.bind(tag=TAG).error(
            f"天气城市搜索失败：HTTP {http_response.status_code}，API code={response.get('code')}"
        )
        raise RuntimeError("city_lookup_failed")
    return response.get("location") or []


def fetch_weather_page(url):
    response = requests.get(url, headers=HEADERS, timeout=10)
    return BeautifulSoup(response.text, "html.parser") if response.ok else None


def parse_weather_info(soup):
    city_name = soup.select_one("h1.c-submenu__location").get_text(strip=True)

    current_abstract = soup.select_one(".c-city-weather-current .current-abstract")
    current_abstract = (
        current_abstract.get_text(strip=True) if current_abstract else "未知"
    )

    current_basic = {}
    for item in soup.select(
        ".c-city-weather-current .current-basic .current-basic___item"
    ):
        parts = item.get_text(strip=True, separator=" ").split(" ")
        if len(parts) == 2:
            key, value = parts[1], parts[0]
            current_basic[key] = value

    temps_list = []
    for row in soup.select(".city-forecast-tabs__row")[:7]:  # 取前7天的数据
        date = row.select_one(".date-bg .date").get_text(strip=True)
        weather_code = (
            row.select_one(".date-bg .icon")["src"].split("/")[-1].split(".")[0]
        )
        weather = WEATHER_CODE_MAP.get(weather_code, "未知")
        temps = [span.get_text(strip=True) for span in row.select(".tmp-cont .temp")]
        high_temp, low_temp = (temps[0], temps[-1]) if len(temps) >= 2 else (None, None)
        temps_list.append((date, weather, high_temp, low_temp))

    return city_name, current_abstract, current_basic, temps_list


def _normalize_place_name(value):
    name = "".join(str(value or "").split()).casefold()
    for suffix in ("特别行政区", "自治州", "自治区", "省", "市", "区", "县"):
        if name.endswith(suffix) and len(name) > len(suffix):
            return name[: -len(suffix)]
    return name


def _weather_status(status, message, **extra):
    result = {"status": status, "message": message, **extra}
    return ActionResponse(Action.REQLLM, json.dumps(result, ensure_ascii=False), None)


def _select_city(candidates, location, adm):
    normalized_location = _normalize_place_name(location)
    normalized_matches = [
        city
        for city in candidates
        if isinstance(city, dict)
        and (
            _normalize_place_name(city.get("name")) == normalized_location
            or str(city.get("id", "")) == str(location)
        )
    ]
    if adm:
        normalized_adm = _normalize_place_name(adm)
        normalized_matches = [
            city
            for city in normalized_matches
            if normalized_adm
            in {
                _normalize_place_name(city.get("adm1")),
                _normalize_place_name(city.get("adm2")),
            }
        ]

    requested_name = "".join(str(location).split()).casefold()
    literal_matches = [
        city
        for city in normalized_matches
        if "".join(str(city.get("name") or "").split()).casefold() == requested_name
        or str(city.get("id", "")) == str(location)
    ]
    if literal_matches:
        matches = literal_matches
    elif requested_name.endswith("市"):
        # The city API often names a prefecture "朝阳" while also returning
        # "朝阳县". A request for "朝阳市" must not match the county.
        matches = [
            city
            for city in normalized_matches
            if not str(city.get("name") or "").endswith(("县", "区"))
        ]
    else:
        matches = normalized_matches

    unique_matches = {str(city.get("id")): city for city in matches}
    return list(unique_matches.values())


@register_function("get_weather", GET_WEATHER_FUNCTION_DESC, ToolType.SYSTEM_CTL)
def get_weather(conn, location: str = None, lang: str = "zh_CN", adm: str = None):
    from core.utils.cache.manager import cache_manager, CacheType
    from core.weather_eval import effective_weather_default_city

    weather_config = conn.config.get("plugins", {}).get("get_weather", {})
    api_host = weather_config.get("api_host", "mj7p3y7naa.re.qweatherapi.com")
    api_key = weather_config.get("api_key", "a861d0d5e7bf4ee1a83d9a9e4f96d4da")
    if location is not None and not isinstance(location, str):
        return _weather_status("city_not_found", "城市参数无效，请用户确认具体城市。")
    if adm is not None and not isinstance(adm, str):
        return _weather_status(
            "city_not_found", "上级地区参数无效，请用户确认省份或上级城市。"
        )
    location = location.strip() if isinstance(location, str) else None
    adm = adm.strip() if isinstance(adm, str) else None
    if not location:
        if adm:
            return _weather_status(
                "need_city", "已指定上级地区，但尚无具体城市，请询问用户城市。"
            )
        default_location = effective_weather_default_city(conn)
        if not isinstance(default_location, str) or not default_location.strip():
            return _weather_status(
                "need_city",
                "当前智能体没有可用的默认城市，请询问用户要查询哪个城市。",
            )
        location = default_location.strip()

    try:
        candidates = fetch_city_info(location, api_key, api_host, adm=adm)
        matches = _select_city(candidates, location, adm)
        if not matches:
            return _weather_status(
                "city_not_found",
                f"没有找到与“{location}”及指定上级地区相符的城市，请用户确认城市。",
            )
        if len(matches) > 1:
            choices = [
                {
                    "city": city.get("name"),
                    "adm1": city.get("adm1"),
                    "adm2": city.get("adm2"),
                }
                for city in matches[:5]
            ]
            return _weather_status(
                "ambiguous_city",
                "找到多个同名城市，尚未取得天气报告。不要提供温度、降水等天气数据；请询问用户具体省份、城市或区县后再查询。",
                candidates=choices,
            )

        city_info = matches[0]
        weather_cache_key = f"full_weather_{city_info['id']}_{lang}"
        cached_weather_report = cache_manager.get(CacheType.WEATHER, weather_cache_key)
        if cached_weather_report:
            return ActionResponse(Action.REQLLM, cached_weather_report, None)

        soup = fetch_weather_page(city_info["fxLink"])
        if not soup:
            raise RuntimeError("weather_page_unavailable")
        city_name, current_abstract, current_basic, temps_list = parse_weather_info(
            soup
        )
    except Exception as exc:
        logger.bind(tag=TAG).error(f"天气查询失败：{type(exc).__name__}")
        return _weather_status("fetch_error", "天气服务暂时无法查询，请稍后再试。")

    weather_report = f"您查询的位置是：{city_name}\n\n当前天气: {current_abstract}\n"

    # 添加有效的当前天气参数
    if current_basic:
        weather_report += "详细参数：\n"
        for key, value in current_basic.items():
            if value != "0":  # 过滤无效值
                weather_report += f"  · {key}: {value}\n"

    # 添加7天预报
    weather_report += "\n未来7天预报：\n"
    for date, weather, high, low in temps_list:
        weather_report += f"{date}: {weather}，气温 {low}~{high}\n"

    # 提示语
    weather_report += "\n（如需某一天的具体天气，请告诉我日期）"

    # 缓存完整的天气报告
    cache_manager.set(CacheType.WEATHER, weather_cache_key, weather_report)

    return ActionResponse(Action.REQLLM, weather_report, None)
