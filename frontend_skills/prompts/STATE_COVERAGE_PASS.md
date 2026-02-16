# Prompt: State Coverage Pass (loading/empty/error)

"""
현재 화면에서 데이터 의존 구간을 식별하고, 각 구간에 대해 다음 상태 UI를 모두 구현해:
- loading: skeleton 또는 spinner
- empty: 설명 + 다음 행동(CTA)
- error: 원인 설명(짧게) + retry

제약:
- 기능/로직 변경 금지
- 상태별 UI 컴포넌트는 재사용 가능하게 만들 것
- 접근성(스크린리더/포커스) 포함

출력:
1) 상태 매트릭스(컴포넌트/섹션 x 상태)
2) 필요한 컴포넌트 목록
3) 코드 변경(diff)
"""
