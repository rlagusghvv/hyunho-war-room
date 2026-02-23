# 머니탐험대 (Money Explorer) — MVP

초등학생 대상 경제 기초 교육 게임형 앱 MVP입니다.

## MVP 포함 기능
- 온보딩(게임 목표 설명)
- 핵심 루프: `벌기(earn) / 쓰기(spend) / 저축(save)` 미션 카드
- 난이도(쉬움/보통/어려움)
- 부모 설정(일일 플레이 시간 제한, 난이도, 효과음 토글)
- 로컬 저장(SharedPreferences)
- 레벨업(저축 코인 기준)

## 기술 스택
- Flutter (Material 3)
- shared_preferences (로컬 상태 저장)

## 실행
```bash
cd kid_econ_mvp
flutter pub get
flutter run
```

## iOS TestFlight 업로드 준비

### 1) 기본 점검
```bash
flutter doctor
```

### 2) iOS 빌드
```bash
cd kid_econ_mvp
flutter build ipa --release
```

### 3) App Store Connect 업로드
- Xcode Organizer 또는 Transporter로 `.ipa` 업로드
- App Store Connect에서 빌드 처리 후 TestFlight 배포

## 앱스토어 제출 전 체크리스트 (MVP)
- [ ] 앱 이름/아이콘/스플래시 교체
- [ ] 개인정보 처리방침 링크 준비
- [ ] 부모 설정 PIN 고정값(현재 1234) 제거
- [ ] 효과음/이미지 에셋 정식 반영
- [ ] 연령 등급/키즈 카테고리 정책 검토

## 구조
- `lib/main.dart`: MVP 전체 로직(단일 파일)

## Post-MVP TODO
- 경제 개념 스테이지 분리(예산/기회비용/지연보상)
- 학습 리포트(부모용 주간 리포트)
- 서버 연동(학습 기록 백업)
- 보상 시스템(뱃지/퀘스트)
- 콘텐츠/아트 리소스 교체
