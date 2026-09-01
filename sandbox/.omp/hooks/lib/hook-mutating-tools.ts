/**
 * 파일을 쓰는 편집 툴의 단일 목록.
 *
 * post 훅 48곳이 같은 목록을 각자 들고 있다가 pi-hashline-edit-pro 도입에서 전부
 * 구멍났다(2026-09-01 실측: 플러그인 replace/insert 편집이 검사 트리거를 우회).
 * 빌트인이든 플러그인이든 "파일을 쓰는 툴"은 여기 한 곳에만 추가한다.
 */
export const FILE_EDIT_TOOLS = ["write", "edit", "replace", "insert", "undo_last_change"] as const;
