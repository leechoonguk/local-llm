# Measured provider behaviour — 식품바코드 품목정보 (service I2570)

Steps 1-2 of `skill://integration` (measurement) are DONE. This file is the result.
Do NOT call the live API. Do NOT re-measure.

## Provider (already seeded, revision 64)

- provider code: `mfds-food-safety-korea`
- secret name: `service-key` (already seeded; reuse it, do not create a provider or secret)
- base_url is already on the provider row

## Transport (measured)

- method: GET
- path template: `/api/{service_key}/{service_id}/{data_type}/{range_start}/{range_end}`
- `service_id` is the literal `I2570`; `data_type` is the literal `json`
- `range_start` / `range_end` are integers supplied by the caller (paging window)
- optional filters are appended as **extra path segments in `변수명=값` form**, not as a query
  string — the provider ignores the query string entirely:
  | wire name | meaning | required |
  |---|---|---|
  | `CHNG_DT` | 변경일자 | no |
  | `PRDLST_REPORT_NO` | 품목제조번호 | no |
  | `PRDT_NM` | 제품명 | no |
  | `BRCD_NO` | 바코드번호 | no |
- timeouts/retries measured against the provider: connect 5000ms, read 15000ms,
  max_retries 2, retry_base 200ms, retry_max 1000ms

## Envelope and paging (measured)

- response wrapper: `{"I2570": { "total_count": "<string>", "row": [ ... ] }}`
- rows live at `/I2570/row`, the total at `/I2570/total_count`
- the provider reports its status at `/I2570/RESULT/CODE`; measured values: `INFO-000` (rows) and `INFO-200` (no rows) — both are non-error

## Response row fields (from the documented 항목 설명)

| wire path | 항목 |
|---|---|
| `/PRDLST_REPORT_NO` | 품목제조번호 |
| `/PRDLST_NM` | 품목명 |
| `/PRDT_NM` | 제품명 |
| `/CMPNY_NM` | 업소명 |
| `/BRCD_NO` | 바코드번호 |
| `/HRNK_PRDLST_NM` | 상위품목분류명 |
| `/HTRK_PRDLST_NM` | 최상위품목분류명 |
| `/LAST_UPDT_DTM` | 최종수정일시 |

## One measured page (raw)

Inputs: `range_start=1`, `range_end=3`, `PRDT_NM=김치`, `BRCD_NO=8801234567890`

```json
{
  "I2570": {
    "total_count": "1475",
    "row": [
      {
        "PRDLST_REPORT_NO": "F2024000123456",
        "PRDLST_NM": "냉동김치",
        "PRDT_NM": "신선배 김치",
        "CMPNY_NM": "(주)김치공방",
        "BRCD_NO": "8801234567890",
        "HRNK_PRDLST_NM": "발효식품",
        "HTRK_PRDLST_NM": "식품",
        "LAST_UPDT_DTM": "2024-01-15 09:30:00.0"
      }
    ],
    "RESULT": {
      "CODE": "INFO-000",
      "MSG": "정상처리되었습니다."
    }
  }
}
```
