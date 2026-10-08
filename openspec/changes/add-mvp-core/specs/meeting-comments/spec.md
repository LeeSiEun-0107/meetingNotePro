# Spec Delta

## Purpose
회의록 한 건에 팀원이 의견을 남기고 읽는 기능이다. 결정에 의견이 있거나 맥락을 묻고 싶을 때 쓴다.

## ADDED Requirements

### Requirement: 댓글 작성
<!-- 근거: D-09, D-10 · detail.html -->
시스템은 팀 멤버가 회의록에 500자 이내 댓글을 남기게 해야 한다(SHALL). 댓글은 회의록 전체에 붙는다. 등록 후 입력칸은 비워지고 새 댓글은 목록 맨 아래에 붙으며 활동 기록에 남는다.

#### Scenario: 댓글 등록
- **WHEN** 팀 멤버가 `POST /api/meetings/{id}/comments` 로 내용을 보낸다
- **THEN** 201 을 돌려주고 화면은 입력칸을 비운 뒤 목록 맨 아래에 새 댓글을 붙인다

#### Scenario: 500자 초과
- **WHEN** 내용이 500자를 넘는다
- **THEN** 400 `VALIDATION_ERROR` 를 돌려준다

#### Scenario: 빈 내용
- **WHEN** 내용이 비어 있다
- **THEN** 400 `VALIDATION_ERROR` 를 돌려준다

### Requirement: 댓글 목록
<!-- 근거: D-01, D-11 · detail.html -->
시스템은 댓글을 작성 시각 오름차순으로 돌려줘야 한다(SHALL). 각 항목은 id, 쓴 사람 id, 쓴 사람 이름, 내용, 작성 시각, 삭제 가능 여부 `can_delete` 를 담는다. 쓴 사람과 owner 만 지울 수 있으므로 `can_delete` 는 서버가 판정한다. 댓글이 없는 것이 기본 상태다.

#### Scenario: 댓글 보기
- **WHEN** 팀 멤버가 `GET /api/meetings/{id}/comments` 를 부른다
- **THEN** 200 과 오래된 순 배열을 돌려주고 내가 쓴 댓글이거나 내가 owner 이면 `can_delete` 가 참이다

#### Scenario: 댓글이 없음
- **WHEN** 댓글이 하나도 없다
- **THEN** 200 과 빈 배열을 돌려주고 화면은 "아직 댓글이 없음"을 보여 준다

### Requirement: 댓글 삭제
<!-- 근거: D-12 · detail.html -->
시스템은 쓴 사람과 팀 owner 만 댓글을 지울 수 있게 해야 한다(SHALL). 지운 댓글은 목록에서 바로 사라진다.

#### Scenario: 쓴 사람이 삭제
- **WHEN** 쓴 사람이 `DELETE /api/comments/{id}` 를 부른다
- **THEN** 204 를 돌려준다

#### Scenario: owner 가 삭제
- **WHEN** 팀 owner 가 남이 쓴 댓글에 같은 요청을 보낸다
- **THEN** 204 를 돌려준다

#### Scenario: 권한 없는 member
- **WHEN** 쓰지 않은 member 가 삭제를 부른다
- **THEN** 403 `FORBIDDEN` 을 돌려준다

#### Scenario: 삭제 버튼 표시
- **WHEN** `can_delete` 가 거짓인 댓글을 그린다
- **THEN** 삭제 버튼을 보여 주지 않는다
