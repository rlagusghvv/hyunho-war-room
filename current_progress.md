# current_progress.md

## 완료된 작업
- 워크스페이스 전체 파일 목록 스캔 완료(`ls -R`).
- iOS IPA 빌드 완료 (Flutter `couplus_mobile`):
  - Output: `coupang-automation/couplus_mobile/build/ios/ipa/couplus_mobile.ipa`
  - Version: `0.1.0` / Build: `45`
- TestFlight 업로드 시도(altool): **실패**
  - 원인: 이미 build number `45`가 업로드되어 있어서 `cfBundleVersion` 중복(409).
- Build number bump: `0.1.0+46`.
- IPA 재빌드 완료: build 46.
- TestFlight 업로드 성공(altool)
  - Delivery UUID: `97fe6979-47d9-4a7d-8834-c4bd84b9f77e`
- iOS 네이티브 기본 서버 주소를 `https://app.splui.com` 으로 변경 (`ApiClient.defaultBaseUrl`).
- Build number bump: `0.1.0+47`.
- IPA 재빌드 완료: build 47.
- TestFlight 업로드 성공(altool)
  - Delivery UUID: `5d5db7de-edce-439e-b313-b6965a7f1e50`

## 현재 상태
- TestFlight 업로드 완료(처리 대기 시간은 App Store Connect 쪽에서 수 분~수십 분 걸릴 수 있음).
- App Store Connect API Key 파일 로컬 존재:
  - `~/.appstoreconnect/private_keys/AuthKey_87GSWAQ5P2.p8`
  - (키 ID: `87GSWAQ5P2`)

## 다음 단계
1) App Store Connect에서 build 47 처리 완료 확인(TestFlight → Builds)
2) TestFlight에서 테스터에게 배포
3) 현호 기기에서 업데이트 후 "현재 서버 주소"가 기본으로 `https://app.splui.com` 인지 확인

## 특이 사항
- Issuer ID를 찾기 위해 다음을 추가 확인했으나 발견 못 함:
  - workspace 내 검색(`rg`로 apiIssuer/altool/issuer 키워드)
  - `coupang-automation/.env`
  - 쉘 히스토리(`~/.zsh_history`, `~/.bash_history` 등)에서 `--apiIssuer` 패턴
  - `~/.appstoreconnect/private_keys` (p8 키 파일만 존재)
- 따라서 현재는 Issuer ID를 외부에서 한 번 제공받아야 업로드 가능.
- 비밀값(issuer id 등)은 출력/로그에 노출되지 않도록 주의.
