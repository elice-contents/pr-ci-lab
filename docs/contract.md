# PR 자동 검증 명세

오로라주식회사 백엔드팀은 좀비 테마 방탈출 행사 ‘퇴근런’의 예약 페이지를 관리합니다.
PR 테스트와 AI 리뷰를 별도로 수행한 뒤, 코드로 통과 여부를 판정합니다.
Git 브랜치와 PR, Python 기초를 알고 있다고 가정합니다.



## 서비스 상황과 데이터
회차별 남은 입장권 수를 표시하는 서비스입니다. `limit`는 입장 정원, `used`는 확정 예약 인원입니다.
`remaining_quota(limit, used)`는 정원 10명·예약 3명이면 7장, 예약 12명이면 0장을 표시합니다.
예약 현황의 집계가 늦어 정원을 초과하더라도 표시 값은 음수가 되면 안 됩니다.
예약을 허용·차단하거나 초과 예약을 취소하는 함수가 아니라 남은 입장권을 표시하는 함수입니다.
잘못된 PR을 검사 실패로 표시하고, 개발자가 수정한 뒤 다시 검증합니다. 자동 코드 복구와 배포 후 롤백은 하지 않습니다.
실제 병합 제한에는 GitHub main 브랜치의 보호 규칙과 필수 체크 설정이 필요합니다.

## 입력과 판정
`python app.py --input data --output output`으로 실행합니다. 기본 경로도 같습니다.
`tests.json`은 정확히 `{"status":"passed"}` 또는 `{"status":"failed"}`입니다.
`review.json`은 정확히 `status`, `decision`, `findings` 세 필드를 가집니다.
`status`는 `ok` 또는 `error`, `decision`은 `approve` 또는 `request_changes`입니다.
`findings`는 배열이고 각 원소는 정확히 다음 네 필드를 가집니다.

| 필드 | 허용 값 |
|---|---|
| `severity` | `high`, `medium`, `low` |
| `file` | 공백이 아닌 내용이 있는 문자열 |
| `line` | 1 이상의 정수. `true`와 `false`는 정수가 아닙니다 |
| `reason` | 공백이 아닌 내용이 있는 문자열 |

빈 `findings`도 유효합니다. 배열의 모든 원소를 검증합니다.
알 수 없는 추가 필드, 잘못된 자료형, 누락 파일, 잘못된 JSON은 입력 오류입니다.

유효한 입력에서는 아래 표 순서로 해당하는 사유를 모두 기록합니다.

| 조건 | 사유 코드 |
|---|---|
| 테스트 실패 | `tests_failed` |
| 리뷰 실행 오류 | `review_error` |
| 변경 요청 | `changes_requested` |
| `high` 발견 1개 이상 | `high_severity` |

사유가 없으면 `PASS`와 종료 코드 `0`, 있으면 `BLOCK`과 종료 코드 `1`입니다.
입력 오류는 `ERROR`, 사유 `invalid_input`, 종료 코드 `2`입니다.
AI가 approve해도 테스트 실패나 high 문제는 차단합니다. medium/low만 있으면 approve를 허용합니다.

## 결과
출력 폴더를 자동 생성하고 UTF-8로 다음 두 파일을 저장합니다.
`summary.json`은 정확히 `verdict`, `reasons`, `high_count`를 가집니다.
`high_count`는 모든 findings 중 high의 수이고, 입력 오류에서는 0입니다.
`result.txt`에는 판정 문자열과 해당하는 모든 사유 코드가 있어야 합니다. 설명 문장은 자유입니다.
입력과 출력이 같은 폴더여도 실행되어야 합니다.

## 제공된 CI와 완성할 CI
교육용 레포의 `.github/workflows/pr-review.yml`에는 `checks` job만 있습니다.
먼저 이 기본 CI로 오류 PR의 테스트 실패와 수정 후 통과를 확인합니다.
그 뒤 같은 워크플로에 `review` job을 추가해 Claude Code 리뷰와 app.py 판정을 연결합니다.
최종 제출은 아래 PR 워크플로 명세를 모두 만족해야 합니다.

## PR 워크플로
`.github/workflows/pr-review.yml`을 작성합니다. job 이름은 `checks`, `review`입니다.
GitHub Actions 문법에 맞는 YAML이어야 합니다.

| 항목 | 규칙 |
|---|---|
| 트리거 | `pull_request`, types `opened`, `synchronize`, `reopened` |
| 전체 권한 | `permissions: {contents: read}`. job에서 확대하지 않습니다 |
| 중복 실행 | PR 번호를 포함한 concurrency group, `cancel-in-progress: true` |
| 실행기 | 두 job 모두 `ubuntu-latest`, `timeout-minutes: 10` |
| Python | 두 job 모두 `actions/setup-python@v5`, `python-version: '3.12'` |
| checkout | `actions/checkout@v4`, `persist-credentials: false` |
| checks | 기본 PR checkout, `python tools/local_tests.py`, 테스트 실패이면 step 종료 1 |
| review 조건 | `needs: checks`, 같은 저장소 PR일 때만 실행 |
| review checkout | `ref: ${{ github.event.pull_request.base.sha }}`, `fetch-depth: 0` |
| Node와 CLI | `actions/setup-node@v4`, Node `'22'`, `npm install -g @anthropic-ai/claude-code@2.1.296` |
| diff 수집 | 환경변수 `PR_HEAD`, `PR_BASE`에 이벤트의 SHA를 전달, 아래 명령 사용 |
| 실제 리뷰 | `python tools/headless_review.py --diff output/pr.diff --out output/review.json` |
| 판정 | base의 `python tools/local_tests.py`, 이어서 `python app.py --input output --output output` |
| API 키 | Headless step의 env에만 `ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}` |
| 아티팩트 | 두 job의 마지막 step에 `actions/upload-artifact@v4`, `if: always()` |
| 아티팩트 경로 | checks는 `output/tests.log`와 `output/tests.json`, review는 `output/` |

diff 수집 step은 다음 순서를 사용합니다. PR_HEAD와 PR_BASE를 run 문자열에 직접 치환하지 않습니다.
```bash
mkdir -p output
git fetch origin "$PR_HEAD"
git diff "$PR_BASE" "$PR_HEAD" -- src tests > output/pr.diff
```
checks와 review의 테스트 의미는 다릅니다. PR 코드는 시크릿 없는 checks에서 실행합니다.
review의 테스트는 신뢰된 base 코드의 검사이며 PR 테스트를 대신하지 않습니다.
review는 PR head를 checkout하거나 실행하지 않습니다. diff만 AI에 전달합니다.
`pull_request_target`, `continue-on-error`, 자동 수정·병합·배포, `--dangerously-skip-permissions`를 사용하지 않습니다.
AI 코멘트 게시 대신 Actions 체크와 아티팩트로 결과를 확인합니다.

## 실제 연동 조건
로컬 모의 실행은 계정과 API 키가 없어도 가능합니다. 실제 AI 호출은 `ANTHROPIC_API_KEY`가 필요합니다.
`--bare`는 대화형 구독 로그인을 사용하지 않습니다. 키는 파일에 저장하지 않습니다.
GitHub 연동은 합성 데이터만 담은 공개 교육용 저장소에서 진행합니다.
공개 origin fetch를 사용하므로 비공개 저장소 인증 방식은 이 실습 범위 밖입니다.
실제 배포 자동화는 하지 않습니다. 사내 적용에서는 배포 승인, 브랜치 보호, fork 정책과 반출 정책을 정해야 합니다.


## 공식 문서
- Claude Code Headless: https://code.claude.com/docs/en/headless
- Claude Code CLI: https://code.claude.com/docs/en/cli-reference
- GitHub Actions 문법: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
확인일: 2026-10-13. CLI는 npm 배포 버전 2.1.296으로 고정합니다.
