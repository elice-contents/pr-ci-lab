# PR 자동 검증 명세

오로라주식회사의 좀비 방탈출 행사 ‘퇴근런’ 예약 페이지를 검증합니다. limit는 회차 정원, used는 확정 예약 인원이며, 남은 입장권은 max(0, limit - used)입니다. 정원 10·예약 12이면 0장을 표시해야 합니다. 잘못된 PR은 실패 체크로 표시하고 개발자가 수정합니다. 자동 코드 복구·병합·배포는 하지 않습니다.

## 판정 게이트

- app.py는 --input, --output 인자를 받습니다. 기본값은 data, output입니다.
- tests.json은 정확히 {"status":"passed"} 또는 {"status":"failed"}입니다.
- review.json은 정확히 status, decision, findings 필드를 가집니다. status는 ok/error, decision은 approve/request_changes, findings는 배열입니다.
- 각 finding은 정확히 severity, file, line, reason 필드를 가집니다. severity는 high/medium/low, file과 reason은 공백이 아닌 내용이 있는 문자열, line은 1 이상의 정수입니다. bool은 정수로 허용하지 않습니다. 빈 findings는 유효하며 모든 원소를 검증합니다.
- 테스트 실패 → tests_failed, 리뷰 status=error → review_error, 변경 요청 → changes_requested, high 발견 → high_severity 순서로 해당하는 사유를 모두 수집합니다.
- 사유 없음은 PASS·종료 0, 사유 있음은 BLOCK·종료 1입니다. approve라도 테스트 실패나 high 문제는 차단합니다. approve이고 medium/low만 있으면 허용합니다.
- 파일 누락·잘못된 JSON·잘못된 자료형·누락/추가 필드는 ERROR, reasons=["invalid_input"], high_count=0, 종료 2입니다.
- 출력 폴더를 자동 생성해 summary.json과 result.txt를 UTF-8로 저장합니다. 입력 오류 때도 저장하고 입력·출력 폴더가 같아도 동작해야 합니다.
- summary.json은 정확히 verdict, reasons, high_count를 가집니다. high_count는 모든 high finding의 개수인 정수입니다. result.txt에 판정과 모든 사유 코드를 기록합니다.

## PR 워크플로

기존 .github/workflows/pr-review.yml의 checks를 유지하고 review job을 추가합니다.

- pull_request의 opened, synchronize, reopened만 사용합니다. PR 번호를 포함한 concurrency group과 cancel-in-progress: true를 설정합니다.
- 전체 permissions는 contents: read이며 job에서 확대하지 않습니다. 두 job 모두 ubuntu-latest, timeout-minutes: 10입니다.
- 두 job에서 actions/checkout@v4와 persist-credentials: false, actions/setup-python@v5와 python-version: '3.12'를 사용합니다.
- checks는 기본 PR checkout으로 python tools/local_tests.py를 실행하고 실패 종료 코드를 유지합니다. secret은 전달하지 않습니다.
- review는 needs: checks이며 if: github.event.pull_request.head.repo.full_name == github.repository입니다.
- review checkout의 ref는 ${{ github.event.pull_request.base.sha }}, fetch-depth는 0입니다. PR head를 checkout하거나 실행하지 않습니다.
- PR_HEAD에는 ${{ github.event.pull_request.head.sha }}, PR_BASE에는 ${{ github.event.pull_request.base.sha }}를 env로 전달하고 아래 명령을 하나의 step으로 실행합니다. SHA를 run 문자열에 직접 치환하지 않습니다.

```bash
mkdir -p output
git fetch origin "$PR_HEAD"
git diff "$PR_BASE" "$PR_HEAD" -- src tests > output/pr.diff
```

- 이어서 아래 세 명령을 각각 별도의 일반 step으로 실행합니다. 조건부 생략과 continue-on-error는 사용하지 않습니다.

```bash
python tools/headless_review.py --diff output/pr.diff --out output/review.json
python tools/local_tests.py
python app.py --input output --output output
```

- 리뷰 step의 env에만 REVIEW_API_KEY: ${{ secrets.REVIEW_API_KEY }}, REVIEW_BASE_URL: https://mlapi.run/75b601aa-4392-442e-b232-b9f7a13c545b/v1, REVIEW_MODEL: anthropic/claude-haiku-4-5를 설정합니다. 전체/job env에 키를 두지 않습니다.
- 각 job의 마지막에 actions/upload-artifact@v4, if: always()를 사용합니다. checks 경로는 output/tests.log와 output/tests.json, review 경로는 output/입니다. 아티팩트 이름은 서로 달라야 합니다.
- review의 테스트는 신뢰된 base 검사이며 PR 테스트를 대신하지 않습니다. pull_request_target, 실패 무시, 자동 수정·병합·배포, dangerously-skip-permissions는 사용하지 않습니다.
- Node와 Claude Code CLI 설치는 CI 리뷰에 필요하지 않습니다. 런박스에서 구현할 때는 Claude Code를 사용하고 실행 명령은 python3를 사용합니다.

## 실제 리뷰와 인증

제공된 tools/headless_review.py는 Reviewer 정의(.claude/agents/reviewer.md)를 프롬프트로 읽고 교육용 OpenAI 호환 API의 /chat/completions를 호출합니다. CLI sub-agent를 실행하지 않습니다.
--mock는 고정 응답으로 연결만 확인합니다. 실제 호출에는 REVIEW_API_KEY, REVIEW_BASE_URL, REVIEW_MODEL이 필요합니다. 키는 본인 포크의 Actions secret에 등록하며 파일·커밋·로그에 저장하지 않습니다.
응답 스키마를 검증하며 인증·호출·응답 오류는 status=error로 저장하고 게이트에서 차단합니다. 최대 출력 토큰은 1500, 요청 제한 시간은 90초이며 사용 한도·비용은 제공자 정책을 따릅니다.
자동 채점은 실제 GitHub·API 호출 성공을 증명하지 않습니다. main 병합 제한에는 브랜치 보호의 필수 체크 설정이 필요합니다. 새 교육용 엔드포인트의 실제 호출은 별도 검증이 필요합니다.
