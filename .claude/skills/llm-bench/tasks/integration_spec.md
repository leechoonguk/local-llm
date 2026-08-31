# Measured provider behaviour — 바코드연계제품정보 (service C005)

Steps 1-2 of `skill://integration` (measurement) are DONE. This file is the result.
Do NOT call the live API. Do NOT re-measure.

## Provider (already seeded, revision 64)

- provider code: `mfds-food-safety-korea`
- operation code: `search-barcode-linked-product` — 이 오퍼레이션의 정체다. 시드 행, `api/integration.<code>.http`,
  픽스처 파일, 시드 마이그레이션 파일명이 모두 이 이름을 따른다(규약은 `.omp/rules/backend-migrations.md`).
- secret name: `service-key` (already seeded; reuse it, do not create a provider or secret)
- base_url is already on the provider row

## Transport (measured)

- method: GET
- path template: `/api/{service_key}/{service_id}/{data_type}/{range_start}/{range_end}`
- `service_id` is the literal `C005`; `data_type` is the literal `json`
- `range_start` / `range_end` are integers supplied by the caller (paging window) — required,
  no default (RANGE 계열: 모든 실행이 창을 명시해야 한다)
- optional filters are appended as **extra path segments in `변수명=값` form**, not as a query
  string — the provider silently ignores a real query string (measured):
  | wire name | meaning | required |
  |---|---|---|
  | `CHNG_DT` | 변경일자 (YYYYMMDD, 8 digits) | no |
  | `PRDLST_REPORT_NO` | 품목제조보고번호 | no |
  | `BAR_CD` | 바코드번호 | no |
- timeouts/retries measured against the provider: connect 5000ms, read 15000ms,
  max_retries 2, retry_base 200ms, retry_max 1000ms

## Envelope and paging (measured)

- response wrapper: `{"C005": { "total_count": "<string>", "row": [ ... ] }}`
- rows live at `/C005/row`, the total at `/C005/total_count`
- the provider reports its status at `/C005/RESULT/CODE`; measured values: `INFO-000` (rows) and `INFO-200` (no rows) — both are non-error; any other code rejects the call

## Response row fields (from the documented 항목 설명)

| wire path | 항목 |
|---|---|
| `/PRDLST_REPORT_NO` | 품목제조보고번호 |
| `/PRMS_DT` | 허가일자 |
| `/END_DT` | 폐지일자 |
| `/PRDLST_NM` | 품목명 |
| `/POG_DAYCNT` | 유통/소비기한 |
| `/PRDLST_DCNM` | 품목유형명 |
| `/BSSH_NM` | 업소명 |
| `/INDUTY_NM` | 업종명 |
| `/SITE_ADDR` | 소재지 |
| `/CLSBIZ_DT` | 폐업일자 |

## One measured page (raw)

Inputs: `range_start=1`, `range_end=3`, `BAR_CD=8801234567890`

```json
{
  "C005": {
    "total_count": "152",
    "row": [
      {
        "PRDLST_REPORT_NO": "20240001001",
        "PRMS_DT": "20240115",
        "END_DT": "",
        "PRDLST_NM": "오뚜기 진라면",
        "POG_DAYCNT": "24개월",
        "PRDLST_DCNM": "즉석식품",
        "BSSH_NM": "오뚜기주식회사",
        "INDUTY_NM": "식품제조가공업",
        "SITE_ADDR": "서울특별시 동작구 남부순환로 230",
        "CLSBIZ_DT": ""
      },
      {
        "PRDLST_REPORT_NO": "20240001002",
        "PRMS_DT": "20240220",
        "END_DT": "",
        "PRDLST_NM": "농심 신라면",
        "POG_DAYCNT": "18개월",
        "PRDLST_DCNM": "즉석식품",
        "BSSH_NM": "농심주식회사",
        "INDUTY_NM": "식품제조가공업",
        "SITE_ADDR": "경기도 용인시 처인구 모현면 농심로 1",
        "CLSBIZ_DT": ""
      },
      {
        "PRDLST_REPORT_NO": "20240001003",
        "PRMS_DT": "20230601",
        "END_DT": "20240601",
        "PRDLST_NM": "삼양식품 순한맛 라면",
        "POG_DAYCNT": "12개월",
        "PRDLST_DCNM": "즉석식품",
        "BSSH_NM": "삼양식품주식회사",
        "INDUTY_NM": "식품제조가공업",
        "SITE_ADDR": "경기도 성남시 분당구 분당내곡로 166",
        "CLSBIZ_DT": "20240601"
      }
    ],
    "RESULT": {
      "CODE": "INFO-000",
      "MSG": "정상처리되었습니다."
    }
  }
}
```
