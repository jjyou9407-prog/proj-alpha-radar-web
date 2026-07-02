Alpha Radar AI Engine v3.1 full watchlist

적용:
1) 기존 engine 폴더의 alpha_radar_engine_v1.py 백업
2) 이 파일로 덮어쓰기
3) engine 폴더에서 실행:
   python alpha_radar_engine_v1.py

변경:
- US watchlist 15개 -> 90개 이상 확대
- KR watchlist 44개 -> 80개 이상 확대
- 한화오션 042660 포함 확인
- 기본 업로드 top_n 30 -> 120 확대
- 실행 시 US/KR 스캔 성공 개수 출력
- 중복 종목코드 자동 제거

중요:
웹 프론트가 Supabase에서 limit(30)으로 읽고 있으면 검색 결과는 여전히 30개만 보일 수 있습니다.
그 경우 app/page.tsx의 .limit(30)을 .limit(120)으로 바꾸면 전체 검색이 살아납니다.
