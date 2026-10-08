# Spec Delta

## Purpose
이메일과 비밀번호로 가입하고 로그인하며, 발급된 토큰으로 본인을 확인하고 내 이름과 비밀번호를 관리하는 기능이다. 다른 모든 기능의 접근 기준이 된다.

## ADDED Requirements

### Requirement: 회원가입
<!-- 근거: B-05~B-11 · login.html -->
시스템은 이메일, 비밀번호, 이름을 받아 계정을 만들고 토큰을 발급해야 한다(SHALL). 비밀번호는 bcrypt 로 해시해 저장한다. 가입은 팀 없이 끝나며 팀은 자동으로 만들어지지 않는다. 초대코드를 함께 보내면 가입 직후 그 팀에 합류를 시도한다.

#### Scenario: 정상 가입
- **WHEN** 형식이 맞는 새 이메일, 8자 이상 비밀번호, 이름으로 `POST /api/auth/signup` 을 부른다
- **THEN** 201 과 JWT 를 돌려주고, 소속 팀은 없다

#### Scenario: 이메일 형식 오류
- **WHEN** `user@@example` 처럼 형식이 틀린 이메일로 가입한다
- **THEN** 400 `EMAIL_INVALID` 를 `{code, msg}` 로 돌려준다

#### Scenario: 이메일 중복
- **WHEN** 이미 가입된 이메일로 가입한다
- **THEN** 409 `EMAIL_DUPLICATED` 를 돌려준다

#### Scenario: 약한 비밀번호
- **WHEN** 8자 미만 비밀번호로 가입한다
- **THEN** 400 `PASSWORD_TOO_WEAK` 를 돌려준다

#### Scenario: 없는 초대코드
- **WHEN** 존재하지 않는 초대코드를 넣고 가입한다
- **THEN** 계정은 만들어지고 404 `INVITE_NOT_FOUND` 로 합류만 실패하며, 사용자는 팀 설정 화면으로 이동한다

### Requirement: 로그인과 토큰
<!-- 근거: B-01~B-04, B-02 · login.html -->
시스템은 이메일과 비밀번호가 맞으면 만료 24시간인 JWT 를 발급해야 한다(SHALL). 갱신 토큰은 없다. 이메일이 존재하는지는 노출하지 않으므로 이메일 오류와 비밀번호 오류는 같은 응답이다.

#### Scenario: 로그인 성공
- **WHEN** 맞는 이메일과 비밀번호로 `POST /api/auth/login` 을 부른다
- **THEN** 200 과 JWT 를 돌려주고, 화면은 토큰을 저장한 뒤 소속 팀이 있으면 회의록 목록으로, 없으면 팀 설정 화면으로 이동한다

#### Scenario: 로그인 실패
- **WHEN** 이메일 또는 비밀번호가 틀리다
- **THEN** 401 `INVALID_CREDENTIALS` 를 돌려주고 어느 쪽이 틀렸는지 알리지 않는다

### Requirement: 토큰 만료 처리
<!-- 근거: B-03 · login.html -->
시스템은 만료된 토큰으로 온 요청에 401 `TOKEN_EXPIRED` 를 돌려줘야 한다(SHALL). 화면은 이 응답을 어느 화면에서 받아도 저장된 토큰을 지우고 로그인 화면으로 보내며, 로그인 화면은 세션 만료 안내를 띄운다.

#### Scenario: 24시간이 지난 토큰
- **WHEN** 발급 24시간이 지난 토큰으로 API 를 부른다
- **THEN** 401 `TOKEN_EXPIRED` 를 받고, 화면은 토큰을 지운 뒤 `/login.html` 로 이동해 "세션 만료" 안내를 보여 준다

#### Scenario: 로그인 화면 밖에서의 만료
- **WHEN** 칸반이나 회의록 화면에서 401 `TOKEN_EXPIRED` 를 받는다
- **THEN** 같은 방식으로 로그인 화면으로 이동한다

### Requirement: 내 정보 조회
<!-- 근거: J-01 · profile.html -->
시스템은 로그인한 사람의 id, 이름, 이메일, 소속 팀 안의 역할(owner 또는 member)을 돌려줘야 한다(SHALL). 이메일은 고칠 수 없다.

#### Scenario: 내 정보 보기
- **WHEN** 유효한 토큰으로 `GET /api/auth/me` 를 부른다
- **THEN** 200 과 `id`, `name`, `email`, `role` 을 돌려준다

### Requirement: 내 이름과 비밀번호 수정
<!-- 근거: J-02~J-06 · profile.html -->
시스템은 이름만 보내면 비밀번호를 그대로 두고, 비밀번호를 보내면 8자 이상일 때만 바꿔야 한다(SHALL). 비밀번호 두 칸이 서로 다르면 화면이 서버로 보내지 않는다. 계정 변경은 활동 기록에 남기지 않는다.

#### Scenario: 이름만 변경
- **WHEN** 이름만 담아 `PUT /api/auth/me` 를 부른다
- **THEN** 200 을 돌려주고 비밀번호는 바뀌지 않는다

#### Scenario: 두 비밀번호가 다름
- **WHEN** 새 비밀번호와 확인 칸이 다르다
- **THEN** 화면이 "두 비밀번호가 다름"을 보여 주고 서버를 부르지 않는다

#### Scenario: 약한 새 비밀번호
- **WHEN** 8자 미만 새 비밀번호로 저장한다
- **THEN** 400 `PASSWORD_TOO_WEAK` 를 돌려준다

#### Scenario: 저장 중 중복 클릭
- **WHEN** 저장 요청이 진행 중이다
- **THEN** 저장 버튼은 잠겨 두 번 눌리지 않는다

### Requirement: 로그아웃
<!-- 근거: 프로그램정의 7-2 로그아웃 · profile.html -->
시스템은 로그아웃 요청에 200 만 돌려줘야 한다(SHALL). 토큰은 무상태라 서버는 차단 목록을 두지 않고, 화면이 저장된 토큰을 지운다.

#### Scenario: 로그아웃
- **WHEN** 내 정보 화면에서 로그아웃을 누른다
- **THEN** `POST /api/auth/logout` 은 200 을 돌려주고 화면은 토큰을 지운 뒤 로그인 화면으로 이동한다
