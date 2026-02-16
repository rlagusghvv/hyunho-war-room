# Prompt: Web (Next.js/React + shadcn/ui/Tailwind) Quality Pass

"""
Next.js/React 코드의 UI 품질을 올려줘. (가능하면 shadcn/ui 또는 Radix 기반 패턴으로 정리)

필수:
- 버튼/인풋/카드/테이블 컴포넌트 variant 통일
- tailwind class 난잡하면 cn() 유틸/variant로 수렴
- empty/loading/error 상태 추가
- 접근성: aria-* / role / focus-visible / label 연결
- 레이아웃: container/max-width/spacing 정리

제약:
- 기능 변경 금지
- 스타일만 바꾸지 말고 상태/접근성까지 완성

출력:
- 변경 사항 요약
- diff
- 남은 TODO
"""
