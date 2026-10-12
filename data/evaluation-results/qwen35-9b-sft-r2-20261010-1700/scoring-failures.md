# 失败明细入口

模型失败见分场景报告：

- [weather](weather/scoring-failures.md)
- [home_switch](home_switch/scoring-failures.md)

运行错误：

```json
[
  {
    "event": "sample_scoring_error",
    "sample_id": "S01-E001-P3",
    "template_id": "S01",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S02-E001-P1",
    "template_id": "S02",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S02-E001-P2",
    "template_id": "S02",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S02-E001-P3",
    "template_id": "S02",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S03-E001-P1",
    "template_id": "S03",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S03-E001-P2",
    "template_id": "S03",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S03-E001-P3",
    "template_id": "S03",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S04-E001-P1",
    "template_id": "S04",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S04-E001-P2",
    "template_id": "S04",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S04-E001-P3",
    "template_id": "S04",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S05-E001-P1",
    "template_id": "S05",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S05-E001-P2",
    "template_id": "S05",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S05-E001-P3",
    "template_id": "S05",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S06-E001-P1",
    "template_id": "S06",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S06-E001-P2",
    "template_id": "S06",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S06-E001-P3",
    "template_id": "S06",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S07-E001-P1",
    "template_id": "S07",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S07-E001-P2",
    "template_id": "S07",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S07-E001-P3",
    "template_id": "S07",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S08-E001-P1",
    "template_id": "S08",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S08-E001-P2",
    "template_id": "S08",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S08-E001-P3",
    "template_id": "S08",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S09-E001-P1",
    "template_id": "S09",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S09-E001-P2",
    "template_id": "S09",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S09-E001-P3",
    "template_id": "S09",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S10-E001-P1",
    "template_id": "S10",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S10-E001-P2",
    "template_id": "S10",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S10-E001-P3",
    "template_id": "S10",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S11-E001-P1",
    "template_id": "S11",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S11-E001-P2",
    "template_id": "S11",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S11-E001-P3",
    "template_id": "S11",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S12-E001-P1",
    "template_id": "S12",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S12-E001-P2",
    "template_id": "S12",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S12-E001-P3",
    "template_id": "S12",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S13-E001-P1",
    "template_id": "S13",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S13-E001-P2",
    "template_id": "S13",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S13-E001-P3",
    "template_id": "S13",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S15-E001-P1",
    "template_id": "S15",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S15-E001-P2",
    "template_id": "S15",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S15-E001-P3",
    "template_id": "S15",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S17-E001-P1",
    "template_id": "S17",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S17-E001-P2",
    "template_id": "S17",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S17-E001-P3",
    "template_id": "S17",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S19-E001-P1",
    "template_id": "S19",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S19-E001-P2",
    "template_id": "S19",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S19-E001-P3",
    "template_id": "S19",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S20-E001-P1",
    "template_id": "S20",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S20-E001-P2",
    "template_id": "S20",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S20-E001-P3",
    "template_id": "S20",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S21-E001-P1",
    "template_id": "S21",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S21-E001-P2",
    "template_id": "S21",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S21-E001-P3",
    "template_id": "S21",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S22-E001-P1",
    "template_id": "S22",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S22-E001-P2",
    "template_id": "S22",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S22-E001-P3",
    "template_id": "S22",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S24-E001-P1",
    "template_id": "S24",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S24-E001-P2",
    "template_id": "S24",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "event": "sample_scoring_error",
    "sample_id": "S24-E001-P3",
    "template_id": "S24",
    "stage": "judge_response",
    "error_code": "invalid_judge_json",
    "exception_type": "ScoringError",
    "message": "本轮评分响应无效",
    "retryable": true,
    "details": {
      "turn": 1,
      "response_length": 0
    },
    "judge_diagnostics": [
      {
        "turn": 1,
        "response_length": 0,
        "response_excerpt": ""
      }
    ],
    "scenario": "weather"
  },
  {
    "stage": "generation",
    "scenario": "home_switch",
    "error_code": "generation_process_failed"
  }
]
```
