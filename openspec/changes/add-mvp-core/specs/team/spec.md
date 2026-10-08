# Spec Delta

## Purpose
팀을 만들고 초대코드로 사람을 모으며, 팀 이름과 멤버를 관리하는 기능이다. 모든 회의록과 할 일은 한 팀 안에서만 공유된다.

## ADDED Requirements

### Requirement: 한 사람은 한 팀에만 속한다
<!-- 근거: 프로그램정의 7-4 소속 팀 수 · team.html F-02 -->
시스템은 한 사용자가 하나의 팀에만 속하도록 해야 한다(SHALL). 소속 팀이 없는 사용자는 회의록 목록 등 팀 화면에 들어갈 수 없고 팀 설정 화면의 팀 만들기와 합류 화면으로 간다.

#### Scenario: 소속 팀 없음
- **WHEN** 팀이 없는 사용자가 로그인한다
- **THEN** 팀 설정 화면에 "아직 소속 팀이 없음"과 팀 만들기, 초대코드 합류 입력이 나오고 회의록 화면으로는 가지 못한다

### Requirement: 팀 생성
<!-- 근거: F-02 · team.html -->
시스템은 팀 이름을 받아 팀을 만들고 만든 사람을 owner 로 등록하며 초대코드를 발급해야 한다(SHALL). 초대코드는 `MN-` 뒤에 4자리 영숫자인 형태이고 팀마다 하나다.

#### Scenario: 팀 만들기
- **WHEN** 소속 팀이 없는 사용자가 팀 이름으로 `POST /api/teams` 를 부른다
- **THEN** 팀이 만들어지고, 그 사용자가 owner 이며, `MN-7K2D` 같은 초대코드가 발급된다

### Requirement: 초대코드로 합류
<!-- 근거: F-02, F-03, F-06 · team.html -->
시스템은 유효한 초대코드를 받으면 그 팀의 member 로 등록해야 한다(SHALL). 코드가 없으면 404 `INVITE_NOT_FOUND`, 정원이 차 있으면 409 `TEAM_FULL` 을 돌려준다. 합류에 실패해도 가입 계정은 그대로 유지한다.

#### Scenario: 정상 합류
- **WHEN** 유효한 코드로 `POST /api/teams/join` 을 부른다
- **THEN** 호출한 사용자가 member 로 등록된다

#### Scenario: 없는 코드
- **WHEN** `MN-0000` 처럼 없는 코드로 합류한다
- **THEN** 404 `INVITE_NOT_FOUND` 를 돌려주고 화면은 입력칸을 붉게 표시한다

#### Scenario: 정원 초과
- **WHEN** 이미 멤버가 6명인 팀에 합류한다
- **THEN** 409 `TEAM_FULL` 을 돌려준다

### Requirement: 팀당 멤버 6명
<!-- 근거: 프로그램정의 ACME Constraints · F-06 · team.html -->
시스템은 팀 멤버를 owner 를 포함해 6명 이내로 제한해야 한다(SHALL). 이 값은 임의로 늘리지 않는다.

#### Scenario: 여섯 번째 멤버
- **WHEN** 멤버가 5명인 팀에 한 명이 합류한다
- **THEN** 합류가 성공하고 멤버 수는 6 / 6 으로 표시된다

### Requirement: 초대코드 재발급
<!-- 근거: F-04, F-05 · team.html -->
시스템은 owner 의 요청으로 초대코드를 새로 발급하고 앞의 코드는 더 쓸 수 없게 해야 한다(SHALL). 이미 합류한 멤버의 멤버십은 영향받지 않는다. 코드는 팀당 하나이고 사람마다 다르게 발급하지 않는다.

#### Scenario: owner 가 재발급
- **WHEN** owner 가 `PUT /api/teams/{id}/code` 를 부른다
- **THEN** 새 코드가 200 으로 돌아오고 이전 코드로 합류하면 404 `INVITE_NOT_FOUND` 이다

#### Scenario: member 가 재발급
- **WHEN** member 가 같은 요청을 부른다
- **THEN** 403 `OWNER_ONLY` 를 돌려준다

### Requirement: 팀 이름 변경
<!-- 근거: F-01, F-07 · team.html -->
시스템은 owner 만 팀 이름을 바꿀 수 있게 해야 한다(SHALL).

#### Scenario: owner 가 이름 변경
- **WHEN** owner 가 `PUT /api/teams/{id}` 로 새 이름을 보낸다
- **THEN** 200 을 돌려주고 이름이 바뀐다

#### Scenario: member 가 이름 변경
- **WHEN** member 가 같은 요청을 보낸다
- **THEN** 403 `OWNER_ONLY` 를 돌려준다

### Requirement: 멤버 목록
<!-- 근거: F-01 · team.html -->
시스템은 팀 멤버마다 id, 이름, 이메일, 역할(owner 또는 member), 배정된 할 일 수 `todo_count` 를 돌려줘야 한다(SHALL). 팀 멤버만 볼 수 있다.

#### Scenario: 멤버 보기
- **WHEN** 팀 멤버가 `GET /api/teams/{id}/members` 를 부른다
- **THEN** 200 과 멤버 배열을 돌려준다

#### Scenario: 다른 팀 사람
- **WHEN** 그 팀의 멤버가 아닌 사용자가 같은 요청을 보낸다
- **THEN** 403 `FORBIDDEN` 을 돌려준다

### Requirement: member 화면의 읽기 전용 표시
<!-- 근거: F-08 · team.html -->
member 로 들어온 사용자의 팀 설정 화면은 읽기만 가능해야 한다(SHALL). owner 전용 조작인 팀 이름 저장, 초대코드 재발급과 복사 버튼은 잠긴 상태로 보인다. 권한 등급은 owner 와 member 둘뿐이다.

#### Scenario: member 로 팀 설정 열기
- **WHEN** member 가 팀 설정 화면을 연다
- **THEN** 팀 이름 입력은 읽기 전용이고 이름 저장, 복사, 재발급 버튼은 눌리지 않는다
