# Spec Delta

## Purpose
팀에서 누가 언제 무엇을 했는지를 최근 순으로 남기고 보여 주는 기능이다. 팀 전체 활동과 내가 한 활동을 따로 본다.

## ADDED Requirements

### Requirement: 기록하는 활동 종류
<!-- 근거: 프로그램정의 6 activities.kind · team.html · profile.html -->
시스템은 활동을 다섯 종류로만 기록해야 한다(SHALL). `meeting_add`(회의록 등록), `todo_assign`(할 일 배정), `todo_done`(할 일 완료), `comment_add`(댓글 작성), `member_join`(팀 합류)이며 이 다섯 외의 값은 만들지 않는다. 계정 정보 변경은 팀 활동이 아니므로 기록하지 않는다.

#### Scenario: 회의록 등록
- **WHEN** 팀 멤버가 회의록을 저장한다
- **THEN** `meeting_add` 활동이 행위자, 대상, 시각과 함께 남는다

#### Scenario: 할 일 배정과 완료
- **WHEN** 할 일의 담당자를 바꾸거나 상태를 `DONE` 으로 바꾼다
- **THEN** 각각 `todo_assign`, `todo_done` 활동이 남는다

#### Scenario: 댓글과 합류
- **WHEN** 댓글을 쓰거나 초대코드로 합류한다
- **THEN** 각각 `comment_add`, `member_join` 활동이 남는다

#### Scenario: 내 정보 변경
- **WHEN** 이름이나 비밀번호를 바꾼다
- **THEN** 활동 기록은 늘지 않는다

### Requirement: 활동 목록
<!-- 근거: F-01 · team.html, J-01, J-07 · profile.html -->
시스템은 활동을 최근 순으로 최대 50건 돌려줘야 한다(SHALL). 각 항목은 id, 종류 `kind`, 행위자 이름 `actor_name`, 서버가 만든 완성 문장 `text`, 시각 `created_at` 을 담고 화면은 `text` 를 그대로 그린다. 팀 활동은 팀 멤버만, 내 활동은 본인만 본다.

#### Scenario: 팀 활동
- **WHEN** 팀 멤버가 `GET /api/teams/{id}/activities` 를 부른다
- **THEN** 200 과 팀의 최근 50건 이하를 최근 순으로 돌려준다

#### Scenario: 내 활동
- **WHEN** `GET /api/me/activities` 를 부른다
- **THEN** 200 과 내가 행위자인 활동만 최근 순으로 돌려준다

#### Scenario: 활동 없음
- **WHEN** 합류 직후라 활동이 없다
- **THEN** 200 과 빈 배열을 돌려주고 화면은 "아직 활동이 없음"을 보여 준다

### Requirement: 활동 종류별 띠 색
<!-- 근거: 프로그램정의 7-2 활동 기록 띠 색 · team.html, profile.html -->
화면은 활동 카드의 좌측 띠 색을 `kind` 로 정해야 한다(SHALL). `meeting_add` 는 blue, `todo_assign` 은 orange, `todo_done` 은 green, `comment_add` 와 `member_join` 은 purple 이다. 팔레트 5색 안에서만 쓰고 카드 배경은 무채색으로 둔다.

#### Scenario: 완료 활동의 색
- **WHEN** `todo_done` 활동을 그린다
- **THEN** 카드 좌측에 green 띠가 붙는다
