# devPort Crawler

devport.kr 크롤링 서비스

## 기술 스택

- **Python 3.11+**
- **FastAPI** - API 프레임워크
- **Google Gemini 2.5 Flash** - LLM 기반 요약/카테고리화
- **SQLAlchemy** - ORM
- **PostgreSQL** - 데이터베이스
- **Playwright** - 웹 스크래핑

## 현재 상태

🚧 **테스트 진행 중**

- ✅ Dev.to 크롤러 - 테스트 완료
- 🚧 Hashnode, Medium, GitHub 크롤러 - 테스트 대기 중

## 주요 기능

### 데이터 소스

1. **개발 블로그**
   - Dev.to 인기 게시글 (최근 7일, 반응 4개 이상) — 전체 본문 fetch
   - Hashnode 추천 아티클 — 전체 마크다운 본문 fetch
   - Medium 프로그래밍 태그 — RSS 콘텐츠

2. **개발자 커뮤니티**
   - Reddit 개발 서브레딧 (링크 게시물 본문 fetch)
   - Hacker News 인기 스토리 (원문 기사 본문 fetch)

3. **GitHub**
   - 트렌딩 저장소 (별 50개 이상)
   - 최근 생성/업데이트된 인기 프로젝트

### 처리 파이프라인

```
크롤링 + 전체 본문 fetch → 중복 제거 → LLM 축약 번역/카테고리화 → 점수 계산 → DB 저장
```

**LLM 통합**
- 한국어 제목/요약 자동 생성 (축약 번역 — 핵심 빠짐없이 전달)
- AI 기반 카테고리 분류 (12개 카테고리) + 태그 생성
- 3개 LLM 프로바이더 지원 (Gemini, OpenAI, Anthropic) — 통일된 시스템 프롬프트
- 배치 처리 (2개 아티클/요청)
- 요약 실패 시 저장 안함 (품질 보장)

## 빠른 시작

```bash
# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정
cp .env.example .env
# .env 파일에서 GEMINI_API_KEY 설정 필요

# 서버 실행
uvicorn app.main:app --reload

# 크롤링 테스트
curl -X POST http://localhost:8000/api/crawl/devto
```

## API 엔드포인트

- `POST /api/crawl/devto` - Dev.to 크롤링
- `POST /api/crawl/hashnode` - Hashnode 크롤링
- `POST /api/crawl/medium` - Medium 크롤링
- `POST /api/crawl/github` - GitHub 크롤링
- `GET /api/health` - 헬스 체크
- `GET /api/stats` - 통계 조회

## 환경 변수

```env
DATABASE_URL=postgresql://user:pass@localhost:5432/devportdb
GEMINI_API_KEY=your-api-key
LLM_PROVIDER=gemini
GITHUB_TOKEN=your-github-token
MIN_REACTIONS_DEVTO=4
```

## 라이센스

MIT
