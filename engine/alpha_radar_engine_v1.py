"""
Alpha Radar AI Engine v7.3 Expanded US/KR Universe
- US: Finnhub live data
- KR: KRX live data via pykrx
- Uploads rankings and alerts to Supabase
- Adds score breakdown fields for frontend analysis cards
- Adds probability-first ranking: win rate, expected return, loss-risk penalty, timing quality gate
- Expands the liquid US universe to 250+ and the KR universe to 440+ candidates
- Adds Crypto spot/swing radar and Futures LONG/SHORT radar via Binance public market data
- Keeps paper trading with separated limits: stock 7, crypto 5, futures 3
- Ranks by profit-first probability-adjusted final_score rather than raw score
- Fixes KR scan safety: robust latest trading-day lookup and blocks US-only upload when KR scan fails

주의: 투자 참고용 점수 엔진입니다. 매수/매도 추천 또는 수익 보장을 하지 않습니다.
"""
from __future__ import annotations

import os
import json
import time
import math
import html
import statistics
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import requests
import pandas as pd
from dotenv import load_dotenv

try:
    from supabase import create_client
except Exception:
    create_client = None

try:
    from pykrx import stock as krx_stock
except Exception:
    krx_stock = None

KST = timezone(timedelta(hours=9))
US_SCORE_BOOST = int(os.getenv("US_SCORE_BOOST", "2"))
CRYPTO_SCORE_BOOST = int(os.getenv("CRYPTO_SCORE_BOOST", "0"))
FUTURES_SCORE_BOOST = int(os.getenv("FUTURES_SCORE_BOOST", "0"))

# v4.1부터 TOP7은 시장별 강제 포함 없이 순수 점수순으로 선정합니다.
MIN_US_IN_TOP7 = 0

US_WATCHLIST = [
    ("NVDA", "엔비디아"),
    ("TSLA", "테슬라"),
    ("PLTR", "팔란티어"),
    ("AMD", "AMD"),
    ("AVGO", "브로드컴"),
    ("SMCI", "슈퍼마이크로컴퓨터"),
    ("AAPL", "애플"),
    ("MSFT", "마이크로소프트"),
    ("AMZN", "아마존"),
    ("GOOGL", "알파벳"),
    ("META", "메타"),
    ("ORCL", "오라클"),
    ("CRM", "세일즈포스"),
    ("NFLX", "넷플릭스"),
    ("UBER", "우버"),
    ("SHOP", "쇼피파이"),
    ("SNOW", "스노우플레이크"),
    ("NOW", "서비스나우"),
    ("PANW", "팔로알토네트웍스"),
    ("CRWD", "크라우드스트라이크"),
    ("MU", "마이크론"),
    ("ARM", "Arm"),
    ("QCOM", "퀄컴"),
    ("INTC", "인텔"),
    ("TSM", "TSMC"),
    ("GE", "GE"),
    ("GEV", "GE버노바"),
    ("CEG", "컨스텔레이션에너지"),
    ("VRT", "버티브"),
    ("ETN", "이튼"),
    ("LLY", "일라이릴리"),
    ("NVO", "노보노디스크"),
    ("JPM", "JP모건"),
    ("BAC", "뱅크오브아메리카"),
    ("GS", "골드만삭스"),
    ("V", "비자"),
    ("MA", "마스터카드"),
    ("COST", "코스트코"),
    ("WMT", "월마트"),
    ("HD", "홈디포"),
    ("DIS", "디즈니"),
    ("BA", "보잉"),
    ("LMT", "록히드마틴"),
    ("RTX", "RTX"),
    ("NOC", "노스럽그루먼"),
    ("CAT", "캐터필러"),
    ("DE", "디어"),
    ("XOM", "엑슨모빌"),
    ("CVX", "셰브론"),
    ("COIN", "코인베이스"),
    ("HOOD", "로빈후드"),
    ("SOFI", "소파이"),
    ("ADBE", "어도비"),
    ("ADSK", "오토데스크"),
    ("ANET", "아리스타네트웍스"),
    ("APP", "앱러빈"),
    ("ASML", "ASML"),
    ("AXON", "액손"),
    ("BKNG", "부킹홀딩스"),
    ("BLK", "블랙록"),
    ("BRK.B", "버크셔해서웨이B"),
    ("C", "씨티그룹"),
    ("DDOG", "데이터독"),
    ("ELF", "e.l.f. 뷰티"),
    ("FISV", "Fiserv"),
    ("FTNT", "포티넷"),
    ("GM", "제너럴모터스"),
    ("HWM", "하우멧"),
    ("IBM", "IBM"),
    ("ISRG", "인튜이티브서지컬"),
    ("JNJ", "존슨앤존슨"),
    ("KO", "코카콜라"),
    ("LIN", "린데"),
    ("MCD", "맥도날드"),
    ("MELI", "메르카도리브레"),
    ("MRVL", "마벨"),
    ("NEE", "넥스테라에너지"),
    ("PEP", "펩시코"),
    ("PG", "P&G"),
    ("PM", "필립모리스"),
    ("RDDT", "레딧"),
    ("RCL", "로얄캐리비안"),
    ("SBUX", "스타벅스"),
    ("SCHW", "찰스슈왑"),
    ("T", "AT&T"),
    ("TJX", "TJX"),
    ("TXN", "텍사스인스트루먼트"),
    ("UNH", "유나이티드헬스"),
    ("UNP", "유니온퍼시픽"),
    ("VRTX", "버텍스"),
    ("WFC", "웰스파고"),
    ("XYZ", "블록"),
]

# v7.3: 업종 편중을 줄이고 실전 유동성이 충분한 미국 대형/중형주를 확장합니다.
# 기존 목록을 앞에 유지하므로 동일 종목은 아래 공통 dedupe 단계에서 한 번만 스캔됩니다.
US_EXPANDED_WATCHLIST = [
    # 반도체 / 하드웨어 / 네트워크
    ("AMAT", "Applied Materials"), ("LRCX", "Lam Research"), ("KLAC", "KLA"),
    ("CDNS", "Cadence Design Systems"), ("SNPS", "Synopsys"), ("MCHP", "Microchip"),
    ("NXPI", "NXP Semiconductors"), ("ON", "ON Semiconductor"), ("MPWR", "Monolithic Power"),
    ("TER", "Teradyne"), ("WDC", "Western Digital"), ("STX", "Seagate"),
    ("DELL", "Dell Technologies"), ("HPQ", "HP"), ("CSCO", "Cisco"),
    ("CLS", "Celestica"), ("ALAB", "Astera Labs"), ("CRDO", "Credo Technology"),
    # 소프트웨어 / 클라우드 / 보안
    ("ACN", "Accenture"), ("INTU", "Intuit"), ("WDAY", "Workday"),
    ("TEAM", "Atlassian"), ("MDB", "MongoDB"), ("NET", "Cloudflare"),
    ("ZS", "Zscaler"), ("OKTA", "Okta"), ("GDDY", "GoDaddy"),
    ("DOCU", "DocuSign"), ("TWLO", "Twilio"), ("HUBS", "HubSpot"),
    ("VEEV", "Veeva Systems"), ("PATH", "UiPath"),
    ("IOT", "Samsara"), ("TEM", "Tempus AI"),
    # 헬스케어 / 바이오 / 의료기기
    ("ABBV", "AbbVie"), ("MRK", "Merck"), ("PFE", "Pfizer"),
    ("BMY", "Bristol Myers Squibb"), ("AMGN", "Amgen"), ("GILD", "Gilead Sciences"),
    ("REGN", "Regeneron"), ("BIIB", "Biogen"), ("MRNA", "Moderna"),
    ("TMO", "Thermo Fisher"), ("DHR", "Danaher"), ("ABT", "Abbott"),
    ("MDT", "Medtronic"), ("SYK", "Stryker"), ("BSX", "Boston Scientific"),
    ("EW", "Edwards Lifesciences"), ("DXCM", "DexCom"), ("PODD", "Insulet"),
    ("IDXX", "IDEXX"), ("HCA", "HCA Healthcare"), ("CI", "Cigna"),
    ("CVS", "CVS Health"), ("ELV", "Elevance Health"), ("HUM", "Humana"),
    # 금융 / 거래소 / 자산운용 / 보험
    ("MS", "Morgan Stanley"), ("AXP", "American Express"), ("COF", "Capital One"),
    ("USB", "US Bancorp"), ("PNC", "PNC Financial"), ("BK", "BNY Mellon"),
    ("STT", "State Street"), ("CME", "CME Group"), ("ICE", "Intercontinental Exchange"),
    ("SPGI", "S&P Global"), ("MCO", "Moody's"), ("AON", "Aon"),
    ("MRSH", "Marsh"), ("CB", "Chubb"), ("PGR", "Progressive"),
    ("ALL", "Allstate"), ("MET", "MetLife"), ("PRU", "Prudential"),
    ("AFL", "Aflac"), ("APO", "Apollo Global"), ("KKR", "KKR"), ("BX", "Blackstone"),
    # 산업재 / 운송 / 방산
    ("HON", "Honeywell"), ("MMM", "3M"), ("EMR", "Emerson Electric"),
    ("ROK", "Rockwell Automation"), ("PH", "Parker Hannifin"), ("IR", "Ingersoll Rand"),
    ("CMI", "Cummins"), ("PCAR", "PACCAR"), ("FDX", "FedEx"), ("UPS", "UPS"),
    ("CSX", "CSX"), ("NSC", "Norfolk Southern"), ("DAL", "Delta Air Lines"),
    ("UAL", "United Airlines"), ("LUV", "Southwest Airlines"),
    # 에너지 / 소재
    ("COP", "ConocoPhillips"), ("EOG", "EOG Resources"), ("SLB", "SLB"),
    ("OXY", "Occidental Petroleum"), ("MPC", "Marathon Petroleum"), ("VLO", "Valero"),
    ("PSX", "Phillips 66"), ("WMB", "Williams"), ("KMI", "Kinder Morgan"),
    ("OKE", "ONEOK"), ("FANG", "Diamondback Energy"), ("HAL", "Halliburton"),
    ("FCX", "Freeport-McMoRan"), ("NUE", "Nucor"), ("STLD", "Steel Dynamics"),
    ("APD", "Air Products"), ("SHW", "Sherwin-Williams"), ("ECL", "Ecolab"),
    # 소비재 / 리테일 / 여행
    ("LOW", "Lowe's"), ("TGT", "Target"), ("NKE", "Nike"),
    ("LULU", "Lululemon"), ("DECK", "Deckers Outdoor"), ("CMG", "Chipotle"),
    ("YUM", "Yum Brands"), ("DPZ", "Domino's"), ("DRI", "Darden Restaurants"),
    ("MAR", "Marriott"), ("HLT", "Hilton"), ("ABNB", "Airbnb"),
    ("EXPE", "Expedia"), ("CCL", "Carnival"), ("NCLH", "Norwegian Cruise Line"),
    ("DASH", "DoorDash"), ("EBAY", "eBay"), ("ETSY", "Etsy"),
    ("ROST", "Ross Stores"), ("DG", "Dollar General"), ("DLTR", "Dollar Tree"),
    ("KHC", "Kraft Heinz"), ("GIS", "General Mills"), ("MDLZ", "Mondelez"),
    ("MNST", "Monster Beverage"), ("CL", "Colgate-Palmolive"), ("KMB", "Kimberly-Clark"),
    # 유틸리티 / 인프라 / 리츠
    ("DUK", "Duke Energy"), ("SO", "Southern Company"), ("AEP", "American Electric Power"),
    ("EXC", "Exelon"), ("SRE", "Sempra"), ("D", "Dominion Energy"),
    ("PEG", "PSEG"), ("PCG", "PG&E"), ("NRG", "NRG Energy"), ("PWR", "Quanta Services"),
    ("AWK", "American Water Works"), ("AMT", "American Tower"), ("PLD", "Prologis"),
    ("EQIX", "Equinix"), ("DLR", "Digital Realty"), ("O", "Realty Income"),
    ("SPG", "Simon Property"), ("VICI", "VICI Properties"), ("WELL", "Welltower"),
]

KR_WATCHLIST = [
    ("005930", "삼성전자"),
    ("000660", "SK하이닉스"),
    ("373220", "LG에너지솔루션"),
    ("005380", "현대차"),
    ("000270", "기아"),
    ("012450", "한화에어로스페이스"),
    ("267260", "HD현대일렉트릭"),
    ("034020", "두산에너빌리티"),
    ("329180", "HD현대중공업"),
    ("010140", "삼성중공업"),
    ("042660", "한화오션"),
    ("009540", "HD한국조선해양"),
    ("086520", "에코프로"),
    ("247540", "에코프로비엠"),
    ("051910", "LG화학"),
    ("006400", "삼성SDI"),
    ("035420", "NAVER"),
    ("035720", "카카오"),
    ("068270", "셀트리온"),
    ("207940", "삼성바이오로직스"),
    ("055550", "신한지주"),
    ("105560", "KB금융"),
    ("086790", "하나금융지주"),
    ("316140", "우리금융지주"),
    ("033780", "KT&G"),
    ("000810", "삼성화재"),
    ("005490", "POSCO홀딩스"),
    ("003670", "포스코퓨처엠"),
    ("096770", "SK이노베이션"),
    ("010130", "고려아연"),
    ("064350", "현대로템"),
    ("011200", "HMM"),
    ("028260", "삼성물산"),
    ("018260", "삼성에스디에스"),
    ("009150", "삼성전기"),
    ("066570", "LG전자"),
    ("034730", "SK"),
    ("003550", "LG"),
    ("017670", "SK텔레콤"),
    ("030200", "KT"),
    ("032640", "LG유플러스"),
    ("011070", "LG이노텍"),
    ("402340", "SK스퀘어"),
    ("003490", "대한항공"),
    ("010620", "HD현대미포"),
    ("267250", "HD현대"),
    ("272210", "한화시스템"),
    ("079550", "LIG넥스원"),
    ("047810", "한국항공우주"),
    ("241560", "두산밥캣"),
    ("042700", "한미반도체"),
    ("058470", "리노공업"),
    ("000100", "유한양행"),
    ("128940", "한미약품"),
    ("251270", "넷마블"),
    ("259960", "크래프톤"),
    ("352820", "하이브"),
    ("112610", "씨에스윈드"),
    ("010950", "S-Oil"),
    ("036570", "엔씨소프트"),
    ("180640", "한진칼"),
    ("011780", "금호석유"),
    ("034220", "LG디스플레이"),
    ("011790", "SKC"),
    ("004020", "현대제철"),
    ("161390", "한국타이어앤테크놀로지"),
    ("006800", "미래에셋증권"),
    ("078930", "GS"),
    ("015760", "한국전력"),
    ("086280", "현대글로비스"),
    ("298040", "효성중공업"),
    ("010120", "LS ELECTRIC"),
    ("006260", "LS"),
    ("138040", "메리츠금융지주"),
    ("326030", "SK바이오팜"),
    ("307950", "현대오토에버"),
    ("036460", "한국가스공사"),
    ("047050", "포스코인터내셔널"),
    ("000720", "현대건설"),
    ("375500", "DL이앤씨"),
]


KR_EXTRA_WATCHLIST = [
    # 반도체 / AI / 부품
    ("000990", "DB하이텍"), ("108320", "LX세미콘"), ("222800", "심텍"),
    ("039030", "이오테크닉스"), ("036930", "주성엔지니어링"), ("240810", "원익IPS"),
    ("214150", "클래시스"), ("215600", "신라젠"), ("086900", "메디톡스"),
    ("196170", "알테오젠"), ("145020", "휴젤"), ("141080", "리가켐바이오"),
    ("028300", "HLB"), ("000250", "삼천당제약"), ("214450", "파마리서치"),
    # 조선 / 해운 / 기자재
    ("071970", "HD현대마린엔진"), ("082740", "한화엔진"), ("077970", "STX엔진"),
    ("071950", "코아스"), ("100090", "SK오션플랜트"), ("034230", "파라다이스"),
    # 방산 / 우주 / 항공
    ("462870", "시프트업"), ("089010", "켐트로닉스"), ("099320", "쎄트렉아이"),
    ("064760", "티씨케이"), ("031980", "피에스케이홀딩스"),
    # 원전 / 전력 / 전선 / 변압기
    ("103590", "일진전기"), ("001440", "대한전선"), ("229640", "LS에코에너지"),
    ("017040", "광명전기"), ("033100", "제룡전기"), ("051600", "한전KPS"),
    ("052690", "한전기술"), ("034590", "인천도시가스"), ("011930", "신성이엔지"),
    # 자동차 / 로봇 / 2차전지 장비
    ("012330", "현대모비스"), ("204320", "HL만도"), ("011210", "현대위아"),
    ("454910", "두산로보틱스"), ("277810", "레인보우로보틱스"), ("348370", "엔켐"),
    ("373170", "엠씨넥스"), ("095340", "ISC"), ("090460", "비에이치"),
    # 금융 / 지주 / 배당
    ("024110", "기업은행"), ("139130", "DGB금융지주"), ("175330", "JB금융지주"),
    ("071050", "한국금융지주"), ("039490", "키움증권"), ("016360", "삼성증권"),
    ("005830", "DB손해보험"), ("032830", "삼성생명"), ("086520", "에코프로"),
    # 소비 / 게임 / 엔터 / 인터넷
    ("041510", "에스엠"), ("122870", "와이지엔터테인먼트"), ("035900", "JYP Ent."),
    ("263750", "펄어비스"), ("293490", "카카오게임즈"), ("181710", "NHN"),
    ("004170", "신세계"), ("008770", "호텔신라"), ("282330", "BGF리테일"),
    # 에너지 / 화학 / 소재
    ("009830", "한화솔루션"), ("010060", "OCI홀딩스"), ("011170", "롯데케미칼"),
    ("004370", "농심"), ("271560", "오리온"), ("097950", "CJ제일제당"),
]


KR_MORE_WATCHLIST = [
    # 원전 / 전력 / 전선 / 변압기 / ESS
    ("083650", "비에이치아이"), ("105840", "우진"), ("032820", "우리기술"),
    ("006910", "보성파워텍"), ("094820", "일진파워"), ("126720", "수산인더스트리"),
    ("189860", "서전기전"), ("199820", "제일일렉트릭"), ("189300", "인텔리안테크"),
    ("001820", "삼화콘덴서"), ("009470", "삼화전기"), ("033240", "자화전자"),
    ("013810", "스페코"), ("001780", "알루코"), ("023160", "태광"),
    ("010660", "화천기계"), ("001470", "삼부토건"), ("004490", "세방전지"),
    # 방산 / 우주 / 항공 / 드론 / 부품
    ("103140", "풍산"), ("003570", "SNT다이내믹스"), ("005870", "휴니드"),
    ("065450", "빅텍"), ("010820", "퍼스텍"), ("101390", "아이엠"),
    ("121600", "나노신소재"), ("214430", "아이쓰리시스템"), ("141000", "비아트론"),
    ("041190", "우리기술투자"), ("064290", "인텍플러스"), ("322310", "오로스테크놀로지"),
    # 조선 / 해양플랜트 / 기자재 / 엔진 / 피팅
    ("075580", "세진중공업"), ("010280", "쌍용정보통신"), ("053260", "금강철강"),
    ("014620", "성광벤드"), ("014940", "오리엔탈정공"), ("099410", "동방선기"),
    ("017960", "한국카본"), ("007660", "이수페타시스"), ("033500", "동성화인텍"),
    ("023350", "한국종합기술"), ("012160", "영흥"), ("017650", "대림제지"),
    # 반도체 장비 / 소재 / 부품 / HBM / PCB
    ("000150", "두산"), ("011070", "LG이노텍"), ("089030", "테크윙"),
    ("084370", "유진테크"), ("319660", "피에스케이"), ("067310", "하나마이크론"),
    ("272290", "이녹스첨단소재"), ("094170", "동운아나텍"), ("213420", "덕산네오룩스"),
    ("090470", "제이스텍"), ("183300", "코미코"), ("281820", "케이씨텍"),
    ("253450", "스튜디오드래곤"), ("078600", "대주전자재료"), ("091700", "파트론"),
    ("033640", "네패스"), ("101160", "월덱스"), ("272110", "케이엔제이"),
    ("171090", "선익시스템"), ("382800", "지앤비에스 에코"), ("297090", "씨에스베어링"),
    ("348210", "넥스틴"), ("357780", "솔브레인"), ("036540", "SFA반도체"),
    ("036810", "에프에스티"), ("272210", "한화시스템"), ("200710", "에이디테크놀로지"),
    # AI / 소프트웨어 / 보안 / 데이터센터 / 클라우드
    ("304100", "솔트룩스"), ("402030", "코난테크놀로지"), ("039980", "폴라리스AI"),
    ("047560", "이스트소프트"), ("377480", "마음AI"), ("108860", "셀바스AI"),
    ("300080", "플리토"), ("355390", "크라우드웍스"), ("053800", "안랩"),
    ("131370", "알서포트"), ("053300", "한국정보인증"), ("053580", "웹케시"),
    ("041020", "폴라리스오피스"), ("030520", "한글과컴퓨터"), ("032500", "케이엠더블유"),
    ("058850", "KTcs"), ("058860", "KTis"), ("032190", "다우데이타"),
    ("012750", "에스원"), ("060250", "NHN KCP"), ("052770", "아이톡시"),
    # 로봇 / 자동화 / 스마트팩토리
    ("108490", "로보티즈"), ("090360", "로보스타"), ("317400", "자비스"),
    ("140670", "알에스오토메이션"), ("090710", "휴림로봇"), ("298380", "에이비엘바이오"),
    ("060720", "KH바텍"), ("215200", "메가스터디교육"), ("131970", "두산테스나"),
    # 바이오 / 헬스케어 대형 성장주
    ("328130", "루닛"), ("348080", "큐라클"), ("199730", "바이오인프라"),
    ("206650", "유바이오로직스"), ("302440", "SK바이오사이언스"), ("237690", "에스티팜"),
    ("085660", "차바이오텍"), ("064550", "바이오니아"), ("182400", "엔케이맥스"),
    # 2차전지 / 소재 / 장비 / 리사이클
    ("278280", "천보"), ("137400", "피엔티"), ("066970", "엘앤에프"),
    ("014680", "한솔케미칼"), ("051370", "인터플렉스"), ("086520", "에코프로"),
    ("006110", "삼아알미늄"), ("095500", "미래나노텍"), ("222080", "씨아이에스"),
    ("317330", "덕산테코피아"), ("382480", "지아이텍"), ("348340", "뉴로메카"),
    # 금융 / 증권 / 보험 / 고배당
    ("001450", "현대해상"), ("000370", "한화손해보험"), ("088350", "한화생명"),
    ("003540", "대신증권"), ("005940", "NH투자증권"), ("016610", "DB금융투자"),
    ("138930", "BNK금융지주"), ("004990", "롯데지주"), ("003410", "쌍용C&E"),
    # 소비 / 엔터 / 미디어 / 게임 / 음식료
    ("192080", "더블유게임즈"), ("095660", "네오위즈"), ("225570", "넥슨게임즈"),
    ("251270", "넷마블"), ("067160", "아프리카TV"), ("214270", "FSN"),
    ("079160", "CJ CGV"), ("035760", "CJ ENM"), ("200130", "콜마비앤에이치"),
    ("161890", "한국콜마"), ("090430", "아모레퍼시픽"), ("051900", "LG생활건강"),
    ("014820", "동원시스템즈"), ("003230", "삼양식품"), ("005180", "빙그레"),
    # 건설 / 인프라 / 철강 / 기계
    ("047040", "대우건설"), ("006360", "GS건설"), ("028050", "삼성엔지니어링"),
    ("014790", "한라"), ("000880", "한화"), ("042670", "HD현대인프라코어"),
    ("267270", "HD현대건설기계"), ("009450", "경동나비엔"), ("010780", "아이에스동서"),
    ("001230", "동국홀딩스"), ("005010", "휴스틸"), ("025860", "남해화학"),
]

KR_EXPANDED_WATCHLIST = [
    # 코스피 대형/중형주 및 경기소비재
    ("000080", "하이트진로"), ("000120", "CJ대한통운"), ("000210", "DL"),
    ("000240", "한국앤컴퍼니"), ("000670", "영풍"), ("001040", "CJ"),
    ("001120", "LX인터내셔널"), ("001430", "세아베스틸지주"), ("001680", "대상"),
    ("002380", "KCC"), ("002790", "아모레G"), ("003090", "대웅"),
    ("003240", "태광산업"), ("003850", "보령"), ("004000", "롯데정밀화학"),
    ("004800", "효성"), ("005300", "롯데칠성"), ("005440", "현대지에프홀딩스"),
    ("005850", "에스엘"), ("006120", "SK디스커버리"), ("006280", "녹십자"),
    ("006650", "대한유화"), ("007070", "GS리테일"), ("007310", "오뚜기"),
    ("007340", "DN오토모티브"), ("008930", "한미사이언스"), ("009240", "한샘"),
    ("009420", "한올바이오파마"), ("009970", "영원무역홀딩스"),
    ("011760", "현대코퍼레이션"), ("012630", "HDC"), ("014530", "극동유화"),
    ("014830", "유니드"), ("016380", "KG스틸"), ("017800", "현대엘리베이"),
    ("018880", "한온시스템"), ("020000", "한섬"), ("020150", "롯데에너지머티리얼즈"),
    ("021240", "코웨이"), ("023530", "롯데쇼핑"), ("025540", "한국단자"),
    ("026960", "동서"), ("029780", "삼성카드"), ("031430", "신세계인터내셔날"),
    ("033270", "유나이티드제약"), ("036420", "콘텐트리중앙"), ("057050", "현대홈쇼핑"),
    ("064960", "SNT모티브"), ("069260", "TKG휴켐스"), ("069620", "대웅제약"),
    ("071840", "롯데하이마트"), ("073240", "금호타이어"), ("079430", "현대리바트"),
    ("081660", "휠라홀딩스"), ("089590", "제주항공"), ("090350", "노루페인트"),
    ("093370", "후성"), ("097230", "HJ중공업"), ("111770", "영원무역"),
    ("114090", "GKL"), ("120110", "코오롱인더"), ("139480", "이마트"),
    ("145720", "덴티움"), ("161000", "애경케미칼"), ("170900", "동아에스티"),
    ("185750", "종근당"), ("192820", "코스맥스"), ("214320", "이노션"),
    ("241590", "화승엔터프라이즈"), ("248070", "솔루엠"),
    ("271940", "일진하이솔루스"), ("280360", "롯데웰푸드"),
    ("294870", "HDC현대산업개발"), ("300720", "한일시멘트"),
    ("336260", "두산퓨얼셀"), ("353200", "대덕전자"),
    ("361610", "SK아이이테크놀로지"), ("383220", "F&F"),
    # 코스닥 반도체 / 헬스케어 / 성장주
    ("005290", "동진쎄미켐"), ("007390", "네이처셀"), ("009520", "포스코엠텍"),
    ("025900", "동화기업"), ("030190", "NICE평가정보"), ("033290", "코웰패션"),
    ("034950", "한국기업평가"), ("036830", "솔브레인홀딩스"), ("038500", "삼표시멘트"),
    ("043150", "바텍"), ("046890", "서울반도체"), ("048410", "현대바이오"),
    ("054950", "제이브이엠"), ("056190", "에스에프에이"), ("058610", "에스피지"),
    ("060370", "LS마린솔루션"), ("065350", "신성델타테크"),
    ("067630", "HLB생명과학"), ("068240", "다원시스"), ("078340", "컴투스"),
    ("082270", "젬백스"), ("083450", "GST"), ("084110", "휴온스글로벌"),
    ("086450", "동국제약"), ("094360", "칩스앤미디어"), ("095610", "테스"),
    ("096530", "씨젠"), ("098460", "고영"), ("101490", "에스앤에스텍"),
    ("102710", "이엔에프테크놀로지"), ("104830", "원익머트리얼즈"),
    ("115450", "HLB테라퓨틱스"), ("122990", "와이솔"), ("131290", "티에스이"),
    ("140410", "메지온"), ("166090", "하나머티리얼즈"), ("178320", "서진시스템"),
    ("192440", "슈피겐코리아"), ("195940", "HK이노엔"),
    ("203650", "드림시큐리티"), ("205470", "휴마시스"), ("206560", "덱스터"),
    ("214180", "헥토이노베이션"), ("226950", "올릭스"), ("230240", "에치에프알"),
    ("232140", "와이아이케이"), ("237880", "클리오"), ("243070", "휴온스"),
    ("253590", "네오셈"), ("267980", "매일유업"), ("290650", "엘앤씨바이오"),
    ("299030", "하나기술"), ("319400", "현대무벡스"), ("323280", "태성"),
    ("365340", "성일하이텍"), ("376300", "디어유"), ("399720", "가온칩스"),
    ("417200", "LS머트리얼즈"), ("425040", "티이엠씨"), ("440110", "파두"),
    ("443060", "HD현대마린솔루션"), ("457190", "이수스페셜티케미컬"),
    ("460850", "동국씨엠"), ("466100", "클로봇"), ("475150", "SK이터닉스"),
]

# v7.4: 한국 사용자 검색 보장용 핵심 인기 종목 보강.
# 점수 랭킹에서 밀려도 검색/Supabase 저장 대상에서 빠지지 않도록 아래 ALWAYS_KEEP_SYMBOLS와 함께 사용합니다.
KR_POPULAR_MUST_WATCHLIST = [
    ("000660", "SK하이닉스"), ("005930", "삼성전자"),
    ("005380", "현대차"), ("000270", "기아"),
    ("012450", "한화에어로스페이스"), ("064350", "현대로템"),
    ("042660", "한화오션"), ("329180", "HD현대중공업"), ("009540", "HD한국조선해양"),
    ("267260", "HD현대일렉트릭"), ("034020", "두산에너빌리티"), ("298040", "효성중공업"),
    ("196170", "알테오젠"), ("003230", "삼양식품"), ("352820", "하이브"),
    ("259960", "크래프톤"), ("277810", "레인보우로보틱스"), ("454910", "두산로보틱스"),
    ("489790", "한화비전"),
]

US_WATCHLIST = US_WATCHLIST + US_EXPANDED_WATCHLIST
KR_WATCHLIST = KR_WATCHLIST + KR_EXTRA_WATCHLIST + KR_MORE_WATCHLIST + KR_EXPANDED_WATCHLIST + KR_POPULAR_MUST_WATCHLIST


CRYPTO_SPOT_WATCHLIST = [
    ("BTCUSDT", "비트코인"), ("ETHUSDT", "이더리움"), ("SOLUSDT", "솔라나"),
    ("BNBUSDT", "BNB"), ("XRPUSDT", "리플"), ("DOGEUSDT", "도지코인"),
    ("ADAUSDT", "에이다"), ("LINKUSDT", "체인링크"), ("AVAXUSDT", "아발란체"),
    ("SUIUSDT", "수이"), ("TONUSDT", "톤코인"), ("TRXUSDT", "트론"),
    ("DOTUSDT", "폴카닷"), ("LTCUSDT", "라이트코인"), ("BCHUSDT", "비트코인캐시"),
    ("UNIUSDT", "유니스왑"), ("AAVEUSDT", "에이브"), ("NEARUSDT", "니어"),
    ("APTUSDT", "앱토스"), ("ARBUSDT", "아비트럼"), ("OPUSDT", "옵티미즘"),
    ("INJUSDT", "인젝티브"), ("ATOMUSDT", "코스모스"), ("FILUSDT", "파일코인"),
    ("ETCUSDT", "이더리움클래식"), ("HBARUSDT", "헤데라"), ("ICPUSDT", "인터넷컴퓨터"),
    ("TIAUSDT", "셀레스티아"), ("JUPUSDT", "주피터"), ("PYTHUSDT", "피스네트워크"),
    ("WIFUSDT", "도그위프햇"), ("PEPEUSDT", "페페"), ("FETUSDT", "페치AI"),
    ("RENDERUSDT", "렌더"), ("TAOUSDT", "비트텐서"), ("SEIUSDT", "세이"),
    ("HYPEUSDT", "하이퍼리퀴드"),
]

FUTURES_WATCHLIST = [
    ("BTCUSDT", "비트코인"), ("ETHUSDT", "이더리움"), ("SOLUSDT", "솔라나"),
    ("BNBUSDT", "BNB"), ("XRPUSDT", "리플"), ("DOGEUSDT", "도지코인"),
    ("SUIUSDT", "수이"), ("LINKUSDT", "체인링크"), ("AVAXUSDT", "아발란체"),
    ("ADAUSDT", "에이다"), ("NEARUSDT", "니어"), ("APTUSDT", "앱토스"),
    ("ARBUSDT", "아비트럼"), ("OPUSDT", "옵티미즘"), ("INJUSDT", "인젝티브"),
    ("TIAUSDT", "셀레스티아"), ("SEIUSDT", "세이"), ("FETUSDT", "페치AI"),
    ("RENDERUSDT", "렌더"), ("PEPEUSDT", "페페"), ("WIFUSDT", "도그위프햇"),
]


def _dedupe_watchlist(items: List[tuple[str, str]]) -> List[tuple[str, str]]:
    """중복 종목코드 제거. 같은 코드가 있으면 앞의 이름을 우선합니다."""
    seen = set()
    out: List[tuple[str, str]] = []
    for symbol, name in items:
        key = symbol.strip().upper()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append((key, name.strip()))
    return out

US_WATCHLIST = _dedupe_watchlist(US_WATCHLIST)
KR_WATCHLIST = _dedupe_watchlist(KR_WATCHLIST)
CRYPTO_SPOT_WATCHLIST = _dedupe_watchlist(CRYPTO_SPOT_WATCHLIST)
FUTURES_WATCHLIST = _dedupe_watchlist(FUTURES_WATCHLIST)

KR_THEME_BOOST: Dict[str, int] = {
    # v5.2: 한국 핵심 테마 가중치 강화. 단, 테마만으로 TOP7에 올라오지 않도록 10점 상한 유지.
    # 반도체 / HBM / 장비 / 소재
    "000660": 8, "005930": 5, "042700": 9, "058470": 7, "009150": 5, "000990": 5,
    "108320": 5, "222800": 5, "039030": 8, "036930": 8, "240810": 8, "095340": 8,
    "089030": 8, "084370": 7, "319660": 7, "067310": 7, "064760": 7, "031980": 6,
    "348210": 7, "357780": 7, "036540": 6, "036810": 6, "200710": 6, "131970": 6,
    # 조선 / 해양플랜트 / 기자재
    "042660": 10, "009540": 9, "329180": 9, "010140": 8, "010620": 8,
    "071970": 8, "082740": 8, "077970": 7, "100090": 6, "075580": 6,
    "014620": 6, "014940": 5, "017960": 5, "033500": 6,
    # 방산 / 우주 / 항공
    "012450": 10, "064350": 9, "079550": 9, "047810": 8, "272210": 8, "489790": 8,
    "103140": 7, "003570": 6, "005870": 6, "065450": 5, "010820": 5, "099320": 7,
    "214430": 6,
    # 원전 / 전력 / 전선 / 변압기
    "034020": 10, "267260": 10, "298040": 9, "010120": 9, "006260": 7,
    "103590": 8, "001440": 7, "229640": 7, "017040": 6, "033100": 8,
    "051600": 7, "052690": 8, "083650": 8, "105840": 6, "032820": 6,
    "006910": 5, "094820": 6, "126720": 5, "189860": 5, "199820": 6,
    # AI / 소프트웨어 / 클라우드 / 보안
    "035420": 5, "035720": 4, "304100": 7, "402030": 7, "039980": 5, "047560": 6,
    "377480": 6, "108860": 5, "300080": 5, "355390": 6, "053800": 5, "030520": 5,
    # 로봇 / 자동화
    "454910": 7, "277810": 8, "108490": 6, "090360": 5, "140670": 5, "090710": 4,
    # 바이오 / 플랫폼 회복 후보
    "207940": 4, "068270": 4, "196170": 6, "145020": 5, "141080": 5, "328130": 6,
}


US_THEME_BOOST: Dict[str, int] = {
    # AI / 반도체 / 데이터센터 / 전력 인프라
    "NVDA": 5, "AVGO": 5, "AMD": 4, "TSM": 4, "QCOM": 3, "MU": 4,
    "ARM": 4, "ANET": 5, "VRT": 5, "ETN": 4, "GEV": 4, "CEG": 4,
    "MRVL": 4, "SMCI": 3, "PLTR": 4, "CRWD": 3, "PANW": 3, "DDOG": 3,
    # 금융/거래 플랫폼 강세 후보
    "COIN": 3, "HOOD": 3, "SOFI": 2, "RDDT": 3, "APP": 3,
}

POSITIVE_WORDS = ["beat", "surge", "raises", "upgrade", "growth", "record", "strong", "contract", "partnership", "ai", "data center", "hbm", "buy"]
NEGATIVE_WORDS = ["miss", "cut", "downgrade", "lawsuit", "probe", "recall", "fraud", "delay", "weak", "sell", "dilution", "offering"]

_KR_INVESTOR_FAILURES = 0
_KR_INVESTOR_DISABLED = False

@dataclass
class ScoreRow:
    symbol: str
    name: str
    market: str
    score: int
    grade: str
    price: float
    entry_price: float
    stop_price: float
    target_price: float
    change_text: str
    reason: str
    beginner_note: str
    decision: str
    risk_level: str
    action_text: str
    trend_score: int
    volume_score: int
    news_score: int
    earnings_score: int
    flow_score: int
    risk_score: int
    timing_score: int = 0
    theme_score: int = 0
    confidence_grade: str = "B"
    rsi14: float = 0.0
    ma20_gap_pct: float = 0.0
    final_score: int = 0
    foreign_score: int = 0
    institution_score: int = 0
    win_rate: float = 0.0
    expected_return: float = 0.0
    loss_risk_score: int = 0
    paper_signal: str = "관찰"
    asset_class: str = "STOCK"      # STOCK / CRYPTO / FUTURES
    trade_type: str = "SWING"       # STOCK_SWING / CRYPTO_SPOT / FUTURES
    side: str = "LONG"              # LONG / SHORT
    leverage: int = 1


@dataclass
class HotNewsItem:
    symbol: str
    name: str
    market: str
    title: str
    summary: str
    url: str
    source: str
    published_at: str
    sentiment: str
    hot_score: int
    matched_keywords: str
    related_symbols: str


def read_config() -> Dict[str, Any]:
    load_dotenv()
    path = os.path.join(os.path.dirname(__file__), "config.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    else:
        cfg = {}
    cfg.setdefault("max_share_price_usd", float(os.getenv("MAX_SHARE_PRICE_USD", "1000")))
    cfg.setdefault("top_n", int(os.getenv("ALPHA_RADAR_TOP_N", "120")))
    cfg.setdefault("scan_interval_minutes", 1)
    cfg.setdefault("push_alert_score", 90)
    cfg.setdefault("markets", ["US", "KR", "CRYPTO", "FUTURES"])
    cfg.setdefault("paper_trading_enabled", os.getenv("ALPHA_RADAR_PAPER_TRADING", "true").lower() == "true")
    cfg.setdefault("paper_trade_amount", float(os.getenv("ALPHA_RADAR_PAPER_TRADE_AMOUNT", "100000")))
    cfg.setdefault("paper_max_positions", int(os.getenv("ALPHA_RADAR_PAPER_MAX_POSITIONS", "15")))
    cfg.setdefault("paper_max_stock_positions", int(os.getenv("ALPHA_RADAR_PAPER_MAX_STOCK_POSITIONS", "7")))
    cfg.setdefault("paper_max_crypto_positions", int(os.getenv("ALPHA_RADAR_PAPER_MAX_CRYPTO_POSITIONS", "5")))
    cfg.setdefault("paper_max_futures_positions", int(os.getenv("ALPHA_RADAR_PAPER_MAX_FUTURES_POSITIONS", "3")))
    cfg.setdefault("paper_min_score", int(os.getenv("ALPHA_RADAR_PAPER_MIN_SCORE", "75")))
    cfg.setdefault("paper_min_timing", int(os.getenv("ALPHA_RADAR_PAPER_MIN_TIMING", "10")))
    cfg.setdefault("price_update_seconds", int(os.getenv("ALPHA_RADAR_PRICE_UPDATE_SECONDS", "20")))
    cfg.setdefault("price_update_limit", int(os.getenv("ALPHA_RADAR_PRICE_UPDATE_LIMIT", "30")))
    # v5.2: 정확도 우선 필터. 점수가 높아도 승률/위험/타이밍이 나쁘면 TOP7에서 밀립니다.
    cfg.setdefault("min_rank_win_rate", float(os.getenv("ALPHA_RADAR_MIN_RANK_WIN_RATE", "54")))
    cfg.setdefault("max_rank_loss_risk", int(os.getenv("ALPHA_RADAR_MAX_RANK_LOSS_RISK", "78")))
    cfg.setdefault("avoid_overheat_rsi", float(os.getenv("ALPHA_RADAR_AVOID_OVERHEAT_RSI", "78")))
    cfg.setdefault("hot_news_enabled", os.getenv("ALPHA_RADAR_HOT_NEWS_ENABLED", "true").lower() == "true")
    cfg.setdefault("hot_news_max_items", int(os.getenv("ALPHA_RADAR_HOT_NEWS_MAX_ITEMS", "40")))
    cfg.setdefault("hot_news_alert_score", int(os.getenv("ALPHA_RADAR_HOT_NEWS_ALERT_SCORE", "78")))
    cfg.setdefault("hot_news_fetch_timeout", float(os.getenv("ALPHA_RADAR_HOT_NEWS_FETCH_TIMEOUT", "4.0")))
    cfg.setdefault("hot_news_lookback_minutes", int(os.getenv("ALPHA_RADAR_HOT_NEWS_LOOKBACK_MINUTES", "720")))
    return cfg


def safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return default
        return float(x)
    except Exception:
        return default


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def parse_change_pct(change_text: str) -> float:
    """'+3.2%' 같은 표시값을 안전하게 숫자로 바꿉니다."""
    try:
        return float(str(change_text or "0").replace("%", "").replace("+", "").strip())
    except Exception:
        return 0.0


def calc_rsi(closes: List[float], period: int = 14) -> float:
    """RSI(14) 계산. 데이터 부족 시 중립값 50 반환."""
    if not closes or len(closes) <= period:
        return 50.0
    gains: List[float] = []
    losses: List[float] = []
    start = max(1, len(closes) - period)
    for i in range(start, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    avg_gain = statistics.mean(gains) if gains else 0.0
    avg_loss = statistics.mean(losses) if losses else 0.0
    if avg_loss <= 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return float(clamp(100 - (100 / (1 + rs)), 0, 100))


def calc_timing_score(closes: List[float], price: float, change_pct: float = 0.0) -> tuple[int, float, float, List[str]]:
    """
    v4.1 핵심: 좋은 회사가 아니라 '지금 들어가기 좋은 자리'를 평가.
    - RSI 40~65: 좋은 눌림/상승 초입으로 가점
    - 20일선 근처 또는 살짝 위: 가점
    - 최근 3~5일 눌림 후 반등: 가점
    - 과열 RSI/20일선 과도 이격/당일 급등: 감점
    """
    bits: List[str] = []
    if price <= 0 or len(closes) < 20:
        return 10, 50.0, 0.0, ["타이밍 데이터 부족"]

    rsi = calc_rsi(closes)
    ma20 = statistics.mean(closes[-20:])
    gap = (price - ma20) / ma20 * 100 if ma20 else 0.0

    score = 8

    if 42 <= rsi <= 58:
        score += 6
        bits.append("RSI 안정권")
    elif 58 < rsi <= 65:
        score += 4
        bits.append("상승추세 유지")
    elif 65 < rsi < 75:
        score += 1
        bits.append("상승 후 과열 확인")
    elif 35 <= rsi < 42:
        score += 3
        bits.append("눌림 회복 후보")
    elif rsi > 75:
        score -= 5
        bits.append("RSI 과열 주의")
    elif rsi < 30:
        score -= 2
        bits.append("약세 과매도")

    if -3 <= gap <= 4:
        score += 6
        bits.append("20일선 근처")
    elif 4 < gap <= 9:
        score += 3
        bits.append("20일선 위 추세")
    elif gap > 15:
        score -= 5
        bits.append("20일선 과도 이격")
    elif gap < -8:
        score -= 3
        bits.append("20일선 하회")

    if len(closes) >= 6:
        five_day = (closes[-1] - closes[-6]) / closes[-6] * 100 if closes[-6] else 0.0
        three_day = (closes[-1] - closes[-4]) / closes[-4] * 100 if closes[-4] else 0.0
        recent_high = max(closes[-10:]) if len(closes) >= 10 else max(closes[-6:])
        pullback_from_high = (price - recent_high) / recent_high * 100 if recent_high else 0.0

        if -8 <= five_day <= 3 and change_pct > -1.5:
            score += 3
            bits.append("최근 눌림목")
        if three_day > 2 and price >= ma20:
            score += 2
            bits.append("단기 반등")
        if -10 <= pullback_from_high <= -3 and price >= ma20 * 0.97:
            score += 2
            bits.append("고점 대비 건강한 눌림")

    if change_pct >= 10:
        score -= 8
        bits.append("당일 급등 추격금지")
    elif change_pct >= 7:
        score -= 5
        bits.append("당일 급등 추격주의")
    elif change_pct >= 5:
        score -= 2
        bits.append("단기 급등 대기")
    elif change_pct <= -5:
        score -= 3
        bits.append("당일 급락 확인필요")

    if not bits:
        bits.append("타이밍 중립")

    return int(clamp(score, 0, 20)), round(rsi, 1), round(gap, 1), bits[:3]


def confidence_grade_from_scores(scores: List[int], final_score: int, timing_score: int, risk_score: int) -> str:
    """점수가 한두 항목에 몰린 종목보다 고르게 강한 종목을 더 신뢰."""
    vals = [safe_float(x) for x in scores if x is not None]
    if not vals:
        return "C"
    avg = statistics.mean(vals)
    spread = statistics.pstdev(vals) if len(vals) >= 2 else 0
    strong_count = sum(1 for x in vals if x >= avg * 0.9)
    if final_score >= 88 and timing_score >= 14 and risk_score >= 7 and spread <= 5.5:
        return "A+"
    if final_score >= 80 and timing_score >= 11 and risk_score >= 6 and strong_count >= max(3, len(vals) // 2):
        return "A"
    if final_score >= 68 and risk_score >= 5:
        return "B"
    return "C"


def get_kr_investor_scores(symbol: str, end: str) -> tuple[int, int, List[str]]:
    """
    pykrx에서 가능하면 최근 외국인/기관 순매수 흐름 반영.
    실패해도 엔진은 계속 돌도록 0점 처리.
    """
    global _KR_INVESTOR_FAILURES, _KR_INVESTOR_DISABLED
    if krx_stock is None or not end or _KR_INVESTOR_DISABLED:
        return 0, 0, []
    try:
        start = (datetime.strptime(end, "%Y%m%d") - timedelta(days=10)).strftime("%Y%m%d")
        df = krx_stock.get_market_trading_value_by_date(start, end, symbol)
        if df is None or df.empty:
            _KR_INVESTOR_FAILURES += 1
            if _KR_INVESTOR_FAILURES >= 3:
                _KR_INVESTOR_DISABLED = True
                print("[KR flow] 수급 API 연속 실패 3회: 이번 실행에서는 수급 조회를 생략합니다.")
            return 0, 0, []
        foreign_col = next((c for c in df.columns if "외국인" in str(c)), None)
        inst_col = next((c for c in df.columns if "기관" in str(c)), None)
        bits: List[str] = []
        f_score = 0
        i_score = 0
        if foreign_col:
            vals = [safe_float(x) for x in df[foreign_col].tail(5).tolist()]
            pos_days = sum(1 for x in vals if x > 0)
            total = sum(vals)
            f_score = int(clamp(pos_days * 1.2 + (2 if total > 0 else 0), 0, 8))
            if f_score >= 5:
                bits.append("외국인 순매수")
        if inst_col:
            vals = [safe_float(x) for x in df[inst_col].tail(5).tolist()]
            pos_days = sum(1 for x in vals if x > 0)
            total = sum(vals)
            i_score = int(clamp(pos_days * 1.1 + (2 if total > 0 else 0), 0, 7))
            if i_score >= 5:
                bits.append("기관 순매수")
        _KR_INVESTOR_FAILURES = 0
        return f_score, i_score, bits
    except Exception as e:
        _KR_INVESTOR_FAILURES += 1
        if _KR_INVESTOR_FAILURES >= 3:
            _KR_INVESTOR_DISABLED = True
            print(f"[KR flow] 수급 API 연속 실패 3회: 이번 실행에서는 수급 조회를 생략합니다. 마지막 오류: {e}")
        return 0, 0, []


def get_grade(score: int) -> str:
    if score >= 90: return "S"
    if score >= 80: return "A"
    if score >= 70: return "B"
    if score >= 60: return "C"
    return "D"


def estimate_atr_pct(closes: List[float], highs: Optional[List[float]] = None, lows: Optional[List[float]] = None) -> float:
    """최근 변동성(ATR 비슷한 값)을 %로 추정합니다. 데이터가 부족하면 일간 등락률 평균으로 대체합니다."""
    if not closes or len(closes) < 15:
        return 4.0

    if highs and lows and len(highs) == len(lows) == len(closes) and len(closes) >= 15:
        trs: List[float] = []
        start = max(1, len(closes) - 14)
        for i in range(start, len(closes)):
            high = safe_float(highs[i])
            low = safe_float(lows[i])
            prev_close = safe_float(closes[i - 1])
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            if tr > 0:
                trs.append(tr)
        if trs and closes[-1] > 0:
            return float(clamp(statistics.mean(trs) / closes[-1] * 100, 1.5, 12.0))

    moves: List[float] = []
    for i in range(max(1, len(closes) - 14), len(closes)):
        prev = closes[i - 1]
        cur = closes[i]
        if prev > 0:
            moves.append(abs((cur - prev) / prev * 100))
    if not moves:
        return 4.0
    return float(clamp(statistics.mean(moves) * 1.7, 1.5, 12.0))


def make_trade_plan(price: float, score: int, closes: Optional[List[float]] = None, highs: Optional[List[float]] = None, lows: Optional[List[float]] = None) -> tuple[float, float, float]:
    """
    v3.3: 3단계 분할매수와 손절가 충돌 방지.
    핵심 규칙:
    - 1차 매수는 현재가 근처 눌림.
    - 2차/3차 매수는 1차보다 아래.
    - 손절가는 반드시 3차 매수가보다 아래에 둡니다.
    - 손절은 장중 터치보다 종가 이탈 기준 안내를 기본으로 합니다.

    프론트가 3차 매수를 entry_price * 0.93 근처로 계산해도,
    stop_price는 entry_price * 0.90 이하가 되도록 방어합니다.
    """
    if price <= 0:
        return 0.0, 0.0, 0.0

    atr_pct = estimate_atr_pct(closes or [], highs, lows)

    if score >= 85:
        entry_pct = 0.985
        min_stop_pct = 9.5
        rr_target = 1.90
        min_target_pct = 16.0
    elif score >= 75:
        entry_pct = 0.975
        min_stop_pct = 10.0
        rr_target = 1.80
        min_target_pct = 16.0
    elif score >= 65:
        entry_pct = 0.965
        min_stop_pct = 10.5
        rr_target = 1.70
        min_target_pct = 15.0
    else:
        entry_pct = 0.950
        min_stop_pct = 11.0
        rr_target = 1.60
        min_target_pct = 14.0

    entry = price * entry_pct

    # 프론트 초보자 3차 매수 기준과 충돌하지 않도록 엔진에서도 같은 개념을 잡는다.
    # US는 변동성이 커서 1차 대비 약 -7%, KR은 약 -6.5%를 3차 후보로 본다.
    assumed_third_entry_pct = 0.93
    third_entry = entry * assumed_third_entry_pct

    # ATR 기반 손절폭. 최소 폭은 확보하되 고변동 종목의 무제한 확대는 막습니다.
    raw_stop_pct = float(clamp(max(min_stop_pct, atr_pct * 2.15), min_stop_pct, 17.0))

    # 손절은 반드시 3차 매수가보다 아래. 3차 대비 최소 3% 추가 여유.
    min_stop_price_below_third = third_entry * 0.97
    stop_by_pct = entry * (1 - raw_stop_pct / 100)
    stop = min(stop_by_pct, min_stop_price_below_third)

    # 그래도 손절폭이 과도하면 초보자에게 부담이 크므로 20%를 하한 한계로 둔다.
    # 단, 3차보다 위로 올라가지는 않게 최종 방어.
    max_loss_stop = entry * 0.80
    stop = max(stop, max_loss_stop)
    if stop >= third_entry:
        stop = third_entry * 0.97

    actual_stop_pct = max(0.0, (entry - stop) / entry * 100)
    target_pct = float(clamp(max(min_target_pct, actual_stop_pct * rr_target), 14.0, 42.0))
    target = entry * (1 + target_pct / 100)

    return entry, stop, target


def plan_meta(price: float, entry: float, stop: float, target: float, side: str = "LONG") -> Dict[str, float]:
    if entry <= 0:
        return {"loss_pct": 0.0, "gain_pct": 0.0, "rr": 0.0}
    is_short = str(side).upper() == "SHORT"
    loss_pct = max(0.0, ((stop - entry) if is_short else (entry - stop)) / entry * 100)
    gain_pct = max(0.0, ((entry - target) if is_short else (target - entry)) / entry * 100)
    rr = gain_pct / loss_pct if loss_pct > 0 else 0.0
    return {"loss_pct": loss_pct, "gain_pct": gain_pct, "rr": rr}


def make_dynamic_action(score: int, entry: float, stop: float, target: float, side: str = "LONG") -> str:
    is_short = str(side).upper() == "SHORT"
    meta = plan_meta(0, entry, stop, target, side)
    prefix = make_action_text(score)
    third_entry = entry * (1.05 if is_short else 0.93) if entry > 0 else 0
    direction_note = "반등 시 추격 숏 금지" if is_short else "급등 시 추격매수 금지"
    stop_note = "손절가는 3차 진입가보다 위" if is_short else "손절가는 3차 진입가보다 아래"
    return (
        f"{prefix} {direction_note}. 손절은 장중 터치보다 종가 이탈 확인 우선. "
        f"초보자는 1차 30% / 2차 30% / 3차 40% 분할 접근. "
        f"{stop_note}({third_entry:.2f})에 둡니다. "
        f"예상 손실폭 {meta['loss_pct']:.1f}%, 기대수익 {meta['gain_pct']:.1f}%, 손익비 {meta['rr']:.2f}:1."
    )


def make_note(score: int, grade: str, reason: str) -> str:
    if score >= 90:
        return f"Alpha Radar 분석 결과: {grade} Grade. 강한 추세와 수급이 동시에 잡힌 핵심 후보입니다. 급등 구간에서는 추격매수보다 분할 진입이 유리합니다."
    if score >= 80:
        return f"Alpha Radar 분석 결과: {grade} Grade. 추세가 강한 편입니다. 눌림목에서 분할매수 후 목표가까지 보유 전략을 고려할 수 있습니다."
    if score >= 70:
        return f"Alpha Radar 분석 결과: {grade} Grade. 매수 후보권입니다. 거래량과 뉴스 흐름이 유지되는지 확인하면서 접근하는 구간입니다."
    if score >= 60:
        return f"Alpha Radar 분석 결과: {grade} Grade. 관심종목 등록 구간입니다. 아직 확정 매수보다는 추가 신호 확인이 필요합니다."
    return f"Alpha Radar 분석 결과: {grade} Grade. 현재는 관망 우위입니다. 추세 전환이나 거래량 증가가 확인될 때까지 기다리는 편이 좋습니다."


def make_decision(score: int) -> str:
    if score >= 92: return "최우선매수"
    if score >= 85: return "강력매수"
    if score >= 76: return "분할매수"
    if score >= 66: return "관찰"
    if score >= 55: return "관망"
    return "회피"


def make_risk_level(score: int) -> str:
    if score >= 90: return "매우낮음"
    if score >= 80: return "낮음"
    if score >= 68: return "보통"
    if score >= 55: return "높음"
    return "매우높음"


def make_action_text(score: int) -> str:
    if score >= 85:
        return "1차 분할매수 가능. 급등 시 추격매수 금지, 눌림목 우선."
    if score >= 75:
        return "매수우위 구간. 분할 접근과 손절가 준수가 중요합니다."
    if score >= 65:
        return "관심종목 등록 후 거래량 유지 여부를 확인하세요."
    if score >= 55:
        return "신규 진입보다 추세 전환 확인이 우선입니다."
    return "리스크가 높은 구간입니다. 신규 진입 보류가 유리합니다."


def finnhub_get(endpoint: str, params: Dict[str, Any]) -> Any:
    token = os.getenv("FINNHUB_API_KEY", "").strip()
    if not token:
        raise RuntimeError("FINNHUB_API_KEY가 없습니다. engine/.env 파일에 키를 넣으세요.")
    params = dict(params)
    params["token"] = token
    url = "https://finnhub.io/api/v1/" + endpoint.lstrip("/")
    r = requests.get(url, params=params, timeout=15)
    if r.status_code == 429:
        raise RuntimeError("Finnhub 무료 호출 제한에 걸렸습니다. 잠시 후 다시 실행하세요.")
    r.raise_for_status()
    return r.json()


BINANCE_SPOT_URL = "https://api.binance.com/api/v3/klines"
BINANCE_FUTURES_URL = "https://fapi.binance.com/fapi/v1/klines"
BINANCE_SPOT_TICKER_URL = "https://api.binance.com/api/v3/ticker/price"
BINANCE_FUTURES_TICKER_URL = "https://fapi.binance.com/fapi/v1/ticker/price"


def binance_klines(symbol: str, interval: str = "1d", limit: int = 120, futures: bool = False) -> tuple[List[float], List[float], List[float], List[float]]:
    """Binance 공개 캔들 데이터. API 키 없이 현재가/추세/거래량 판단용으로만 사용합니다."""
    url = BINANCE_FUTURES_URL if futures else BINANCE_SPOT_URL
    r = requests.get(url, params={"symbol": symbol, "interval": interval, "limit": limit}, timeout=15)
    r.raise_for_status()
    data = r.json()
    closes = [safe_float(x[4]) for x in data]
    highs = [safe_float(x[2]) for x in data]
    lows = [safe_float(x[3]) for x in data]
    volumes = [safe_float(x[5]) for x in data]
    return closes, highs, lows, volumes


def binance_current_price(symbol: str, futures: bool = False) -> float:
    """실제 화면 표시용 현재가.

    기존 코드는 klines의 마지막 종가를 현재가처럼 사용했습니다.
    특히 선물 4시간봉에서는 봉이 닫히기 전까지 가격이 크게 뒤처질 수 있어
    ticker/price 값을 우선 사용합니다.
    """
    url = BINANCE_FUTURES_TICKER_URL if futures else BINANCE_SPOT_TICKER_URL
    r = requests.get(url, params={"symbol": symbol}, timeout=8)
    r.raise_for_status()
    return safe_float(r.json().get("price"))


def score_crypto_spot(symbol: str, name: str) -> Optional[ScoreRow]:
    """코인 현물/스윙: 주식 랭킹과 섞이더라도 별도 asset_class로 구분됩니다."""
    try:
        closes, highs, lows, volumes = binance_klines(symbol, interval="1d", limit=120, futures=False)
        if len(closes) < 50 or closes[-1] <= 0:
            return None
        price = binance_current_price(symbol, futures=False) or closes[-1]
        closes[-1] = price
        prev = closes[-2]
        change_pct = (price - prev) / prev * 100 if prev else 0.0
        sma20 = statistics.mean(closes[-20:])
        sma50 = statistics.mean(closes[-50:])
        trend_score = 7
        if price > sma20: trend_score += 5
        if price > sma50: trend_score += 5
        if sma20 > sma50: trend_score += 4
        if 0 < change_pct < 6: trend_score += 2
        if change_pct >= 10: trend_score -= 3
        trend_score = int(clamp(trend_score, 0, 20))

        avgv = statistics.mean(volumes[-20:]) or 1
        volume_ratio = volumes[-1] / avgv
        volume_score = int(clamp(6 + (volume_ratio - 1) * 6, 0, 15))
        timing_score, rsi14, ma20_gap_pct, timing_bits = calc_timing_score(closes, price, change_pct)

        # 코인은 뉴스/실적 대신 시장품질/메이저 안정성으로 보수 점수
        bluechip = 6 if symbol in {"BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "LINKUSDT"} else 3
        news_score = int(clamp(5 + bluechip, 0, 10))
        earnings_score = 6
        flow_score = int(clamp(5 + max(0, volume_ratio - 1) * 3 + max(0, change_pct) * 0.35, 0, 10))
        atr_pct = estimate_atr_pct(closes, highs, lows)
        risk_score = int(clamp(10 - max(0, atr_pct - 5) * 0.7 - max(0, abs(change_pct) - 8) * 0.4, 0, 10))
        theme_score = 3 if symbol in {"BTCUSDT", "ETHUSDT", "SOLUSDT"} else 1
        total = int(clamp(trend_score + volume_score + news_score + earnings_score + flow_score + risk_score + timing_score + theme_score + CRYPTO_SCORE_BOOST, 0, 100))

        bits = ["코인 현물/스윙", *timing_bits]
        if volume_score >= 11: bits.append("거래량 증가")
        if risk_score <= 4: bits.append("변동성 주의")
        reason = " + ".join(bits[:5])
        grade = get_grade(total)
        entry, stop, target = make_trade_plan(price, total, closes, highs, lows)
        confidence = confidence_grade_from_scores([trend_score, volume_score, news_score, flow_score, timing_score], total, timing_score, risk_score)
        return ScoreRow(
            symbol=symbol, name=name, market="CRYPTO", score=total, grade=grade,
            price=round(price, 6), entry_price=round(entry, 6), stop_price=round(stop, 6), target_price=round(target, 6),
            change_text=f"{change_pct:+.1f}%", reason=reason, beginner_note=make_note(total, grade, reason),
            decision=make_decision(total), risk_level=make_risk_level(total), action_text=make_dynamic_action(total, entry, stop, target),
            trend_score=trend_score, volume_score=volume_score, news_score=news_score, earnings_score=earnings_score,
            flow_score=flow_score, risk_score=risk_score, timing_score=timing_score, theme_score=theme_score,
            confidence_grade=confidence, rsi14=rsi14, ma20_gap_pct=ma20_gap_pct, final_score=total,
            asset_class="CRYPTO", trade_type="CRYPTO_SPOT", side="LONG", leverage=1,
        )
    except Exception as e:
        print(f"[CRYPTO skip] {symbol}: {e}")
        return None


def score_futures_pair(symbol: str, name: str, side: str) -> Optional[ScoreRow]:
    """선물 탭용 LONG/SHORT 신호. 실제 주문 없이 모의투자/신호 검증 전용."""
    try:
        closes, highs, lows, volumes = binance_klines(symbol, interval="4h", limit=120, futures=True)
        if len(closes) < 60 or closes[-1] <= 0:
            return None
        price = binance_current_price(symbol, futures=True) or closes[-1]
        closes[-1] = price
        prev = closes[-2]
        change_pct = (price - prev) / prev * 100 if prev else 0.0
        sma20 = statistics.mean(closes[-20:])
        sma60 = statistics.mean(closes[-60:])
        rsi14 = calc_rsi(closes)
        ma20_gap_pct = (price - sma20) / sma20 * 100 if sma20 else 0.0
        avgv = statistics.mean(volumes[-20:]) or 1
        volume_ratio = volumes[-1] / avgv
        atr_pct = estimate_atr_pct(closes, highs, lows)

        is_long = side == "LONG"
        trend_score = 8
        if is_long:
            if price > sma20: trend_score += 5
            if price > sma60: trend_score += 4
            if sma20 > sma60: trend_score += 3
            timing_score = 8
            if 45 <= rsi14 <= 66: timing_score += 5
            if -2 <= ma20_gap_pct <= 6: timing_score += 5
            if 0 < change_pct < 4: timing_score += 2
            if rsi14 > 76 or ma20_gap_pct > 14: timing_score -= 6
            signal_bits = ["선물 LONG 신호"]
        else:
            if price < sma20: trend_score += 5
            if price < sma60: trend_score += 4
            if sma20 < sma60: trend_score += 3
            timing_score = 8
            if 34 <= rsi14 <= 58: timing_score += 4
            if -6 <= ma20_gap_pct <= 2: timing_score += 5
            if -4 < change_pct < 0: timing_score += 2
            if rsi14 < 24 or ma20_gap_pct < -14: timing_score -= 5
            signal_bits = ["선물 SHORT 신호"]
        trend_score = int(clamp(trend_score, 0, 20))
        timing_score = int(clamp(timing_score, 0, 20))
        volume_score = int(clamp(6 + (volume_ratio - 1) * 6, 0, 15))
        news_score = 5
        earnings_score = 5
        flow_score = int(clamp(5 + max(0, volume_ratio - 1) * 4, 0, 10))
        risk_score = int(clamp(10 - max(0, atr_pct - 4) * 0.9 - max(0, abs(change_pct) - 5) * 0.6, 0, 10))
        theme_score = 2 if symbol in {"BTCUSDT", "ETHUSDT", "SOLUSDT"} else 0
        total = int(clamp(trend_score + volume_score + news_score + earnings_score + flow_score + risk_score + timing_score + theme_score + FUTURES_SCORE_BOOST, 0, 100))
        if volume_score >= 11: signal_bits.append("거래량 동반")
        if risk_score <= 4: signal_bits.append("고변동성 주의")
        signal_bits.append(f"RSI {rsi14:.1f}")
        reason = " + ".join(signal_bits[:5])
        grade = get_grade(total)
        entry, stop, target = make_trade_plan(price, total, closes, highs, lows)
        if not is_long:
            # 숏은 목표/손절 방향을 반대로 표시
            stop = entry * (1 + max(0.05, (entry - stop) / entry))
            target = entry * (1 - max(0.07, (target - entry) / entry * 0.55))
        confidence = confidence_grade_from_scores([trend_score, volume_score, flow_score, timing_score], total, timing_score, risk_score)
        return ScoreRow(
            symbol=f"{symbol}-{side}", name=f"{name} {side}", market="FUTURES", score=total, grade=grade,
            price=round(price, 6), entry_price=round(entry, 6), stop_price=round(stop, 6), target_price=round(target, 6),
            change_text=f"{change_pct:+.1f}%", reason=reason, beginner_note=make_note(total, grade, reason),
            decision=make_decision(total), risk_level=make_risk_level(total), action_text=make_dynamic_action(total, entry, stop, target, side),
            trend_score=trend_score, volume_score=volume_score, news_score=news_score, earnings_score=earnings_score,
            flow_score=flow_score, risk_score=risk_score, timing_score=timing_score, theme_score=theme_score,
            confidence_grade=confidence, rsi14=round(rsi14,1), ma20_gap_pct=round(ma20_gap_pct,1), final_score=total,
            asset_class="FUTURES", trade_type="FUTURES", side=side, leverage=3,
        )
    except Exception as e:
        print(f"[FUTURES skip] {symbol} {side}: {e}")
        return None


def score_us(symbol: str, name: str, max_price: float) -> Optional[ScoreRow]:
    q = finnhub_get("quote", {"symbol": symbol})
    price = safe_float(q.get("c"))
    change_pct = safe_float(q.get("dp"))
    if price <= 0 or price > max_price:
        return None

    to_ts = int(datetime.now(timezone.utc).timestamp())
    from_ts = int((datetime.now(timezone.utc) - timedelta(days=120)).timestamp())
    closes: List[float] = []
    volumes: List[float] = []
    highs: List[float] = []
    lows: List[float] = []
    try:
        candles = finnhub_get("stock/candle", {"symbol": symbol, "resolution": "D", "from": from_ts, "to": to_ts})
        if candles.get("s") == "ok":
            closes = [safe_float(x) for x in candles.get("c", [])]
            volumes = [safe_float(x) for x in candles.get("v", [])]
            highs = [safe_float(x) for x in candles.get("h", [])]
            lows = [safe_float(x) for x in candles.get("l", [])]
    except Exception:
        pass

    timing_score, rsi14, ma20_gap_pct, timing_bits = calc_timing_score(closes, price, change_pct)

    if len(closes) >= 50:
        sma20 = statistics.mean(closes[-20:])
        sma50 = statistics.mean(closes[-50:])
        trend_score = 7
        if price > sma20: trend_score += 5
        if price > sma50: trend_score += 5
        if sma20 > sma50: trend_score += 5
        if len(closes) >= 21 and closes[-1] > closes[-20]: trend_score += 3
        if change_pct > 1.5: trend_score += 2
        trend_score = int(clamp(trend_score, 0, 25))
    else:
        trend_score = int(clamp(10 + change_pct * 1.2, 0, 25))

    if len(volumes) >= 20 and volumes[-1] > 0:
        avgv = statistics.mean(volumes[-20:]) or 1
        volume_ratio = volumes[-1] / avgv
        volume_score = int(clamp(7 + (volume_ratio - 1) * 7, 0, 20))
    else:
        volume_score = int(clamp(7 + abs(change_pct), 0, 20))

    news_score = 7
    risk_penalty = 0
    reason_bits: List[str] = []
    try:
        today = datetime.now(timezone.utc).date()
        news = finnhub_get("company-news", {"symbol": symbol, "from": str(today - timedelta(days=7)), "to": str(today)})
        text_news = " ".join([(n.get("headline", "") + " " + n.get("summary", "")) for n in news[:15]]).lower()
        pos = sum(1 for w in POSITIVE_WORDS if w in text_news)
        neg = sum(1 for w in NEGATIVE_WORDS if w in text_news)
        news_score = int(clamp(6 + pos * 2 - neg * 3, 0, 15))
        risk_penalty += min(10, neg * 3)
        if pos > neg: reason_bits.append("긍정 뉴스 우위")
        if neg >= 2: reason_bits.append("악재 뉴스 주의")
    except Exception:
        pass

    earnings_score = 8
    try:
        earnings = finnhub_get("stock/earnings", {"symbol": symbol, "limit": 4})
        surprises = [safe_float(e.get("surprisePercent")) for e in earnings if e.get("surprisePercent") is not None]
        if surprises:
            avg_surprise = statistics.mean(surprises[:4])
            earnings_score = int(clamp(7 + avg_surprise / 3, 0, 15))
            if avg_surprise > 0: reason_bits.append("실적 서프라이즈 양호")
    except Exception:
        pass

    flow_score = 8
    try:
        recs = finnhub_get("stock/recommendation", {"symbol": symbol})
        if recs:
            latest = recs[0]
            buy = safe_float(latest.get("buy")) + safe_float(latest.get("strongBuy")) * 1.5
            sell = safe_float(latest.get("sell")) + safe_float(latest.get("strongSell")) * 1.5
            total_rec = buy + sell + safe_float(latest.get("hold")) + 1
            flow_score = int(clamp(6 + (buy - sell) / total_rec * 13 + max(0, change_pct) * 0.6, 0, 15))
            if buy > sell: reason_bits.append("애널리스트 매수 우위")
    except Exception:
        flow_score = int(clamp(7 + max(0, change_pct) * 1.0, 0, 15))

    risk_score = int(clamp(10 - risk_penalty - max(0, ma20_gap_pct - 18) * 0.2, 0, 10))
    theme_score = US_THEME_BOOST.get(symbol, 0)

    old_component_sum = trend_score + volume_score + news_score + earnings_score + flow_score + risk_score
    total = int(clamp(old_component_sum * 0.72 + timing_score + theme_score + US_SCORE_BOOST, 0, 100))

    if trend_score >= 20: reason_bits.append("추세 강함")
    if volume_score >= 15: reason_bits.append("거래량 증가")
    if theme_score >= 4: reason_bits.append("핵심 테마")
    reason_bits.extend(timing_bits)
    if not reason_bits: reason_bits.append("대형주 관찰 대상")

    grade = get_grade(total)
    entry, stop, target = make_trade_plan(price, total, closes, highs, lows)
    meta = plan_meta(price, entry, stop, target)
    confidence = confidence_grade_from_scores(
        [trend_score, volume_score, news_score, earnings_score, flow_score, timing_score],
        total, timing_score, risk_score
    )
    success_prob = int(clamp(38 + total * 0.34 + timing_score * 0.7 + min(meta["rr"], 3) * 3 - max(0, change_pct - 6) * 2, 35, 86))
    reason_bits.append(f"성공확률 {success_prob}% 추정")
    reason = " + ".join(reason_bits[:5])
    return ScoreRow(
        symbol=symbol, name=name, market="US", score=total, grade=grade,
        price=round(price, 2), entry_price=round(entry, 2), stop_price=round(stop, 2), target_price=round(target, 2),
        change_text=f"{change_pct:+.1f}%", reason=reason, beginner_note=make_note(total, grade, reason),
        decision=make_decision(total), risk_level=make_risk_level(total), action_text=make_dynamic_action(total, entry, stop, target),
        trend_score=trend_score, volume_score=volume_score, news_score=news_score, earnings_score=earnings_score,
        flow_score=flow_score, risk_score=risk_score, timing_score=timing_score, theme_score=theme_score,
        confidence_grade=confidence, rsi14=rsi14, ma20_gap_pct=ma20_gap_pct, final_score=total,
        foreign_score=0, institution_score=0,
    )

def previous_business_date_str() -> str:
    d = datetime.now(KST).date()
    # 한국장은 당일 장 마감/데이터 반영 전이면 pykrx가 빈 데이터를 줄 수 있음.
    # 그래서 기본값은 "오늘이 평일이어도 전일"까지 안전하게 허용한다.
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y%m%d")


def kr_date_candidates(days_back: int = 12) -> List[str]:
    """KRX 데이터가 비어있는 날을 피하기 위해 최근 영업일 후보를 넉넉히 만든다."""
    d = datetime.now(KST).date()
    out: List[str] = []
    for _ in range(days_back + 8):
        if d.weekday() < 5:
            out.append(d.strftime("%Y%m%d"))
        d -= timedelta(days=1)
        if len(out) >= days_back:
            break
    return out


def get_kr_ohlcv_naver(symbol: str, count: int = 140):
    """네이버 공개 차트에서 KR 일봉을 빠르게 가져옵니다.

    종목별 KRX 재시도 폭증을 막기 위한 가격 데이터 경로이며, 외국인/기관
    수급은 기존 pykrx 경로를 그대로 사용합니다.
    """
    url = "https://fchart.stock.naver.com/sise.nhn"
    response = requests.get(
        url,
        params={"symbol": symbol, "timeframe": "day", "count": count, "requestType": 0},
        timeout=10,
        headers={"User-Agent": "Mozilla/5.0 AlphaRadar/7.3"},
    )
    response.raise_for_status()
    # ElementTree는 XML 선언의 EUC-KR 멀티바이트 인코딩을 직접 처리하지
    # 못하므로 먼저 문자열로 디코딩하고 선언부를 제거합니다.
    xml_text = response.content.decode("euc-kr", errors="replace")
    if "?>" in xml_text:
        xml_text = xml_text.split("?>", 1)[1]
    root = ET.fromstring(xml_text)
    records: List[Dict[str, Any]] = []
    for item in root.findall(".//item"):
        parts = str(item.attrib.get("data", "")).split("|")
        if len(parts) != 6:
            continue
        date_text, open_, high, low, close, volume = parts
        records.append({
            "날짜": date_text,
            "시가": safe_float(open_),
            "고가": safe_float(high),
            "저가": safe_float(low),
            "종가": safe_float(close),
            "거래량": safe_float(volume),
        })
    if len(records) < 20:
        return None, ""
    frame = pd.DataFrame(records)
    frame.index = pd.to_datetime(frame.pop("날짜"), format="%Y%m%d")
    return frame, frame.index[-1].strftime("%Y%m%d")


def get_kr_ohlcv_safe(symbol: str, lookback_days: int = 120):
    """
    pykrx가 당일/휴장/데이터 미반영일에 빈 DataFrame을 줄 때가 있어서
    최근 영업일 후보를 뒤로 밀면서 유효한 OHLCV를 찾는다.
    """
    try:
        frame, end = get_kr_ohlcv_naver(symbol, count=max(80, lookback_days))
        if frame is not None and not frame.empty and len(frame) >= 20:
            return frame, end
    except Exception as exc:
        print(f"[KR naver fallback] {symbol}: {type(exc).__name__}: {exc}")

    if krx_stock is None:
        return None, ""
    last_error = ""
    # 유효 종목은 첫 조회에서 대부분 반환됩니다. 빈 종목을 12일씩 재조회하면
    # 확장 유니버스에서 실행 시간이 폭증하므로 최근 4영업일까지만 확인합니다.
    for end in kr_date_candidates(4):
        start = (datetime.strptime(end, "%Y%m%d") - timedelta(days=lookback_days)).strftime("%Y%m%d")
        try:
            df = krx_stock.get_market_ohlcv_by_date(start, end, symbol)
            if df is not None and not df.empty and len(df) >= 20:
                return df, end
            last_error = f"empty dataframe end={end}"
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            continue
    print(f"[KR data fail] {symbol}: {last_error}")
    return None, ""


def get_kr_current_quote_naver(symbol: str) -> tuple[float, float]:
    """네이버 실시간 quote에서 한국 주식 현재가와 등락률을 가져옵니다.

    OHLCV는 일봉 계산용으로 유지하고, 화면 표시/진입 계산용 가격은
    장중 현재가를 우선 사용합니다.
    """
    url = "https://polling.finance.naver.com/api/realtime"
    response = requests.get(
        url,
        params={"query": f"SERVICE_ITEM:{symbol}"},
        timeout=8,
        headers={"User-Agent": "Mozilla/5.0 AlphaRadar/7.4"},
    )
    response.raise_for_status()
    payload = response.json()
    datas = (((payload.get("result") or {}).get("areas") or [{}])[0].get("datas") or [])
    if not datas:
        return 0.0, 0.0
    item = datas[0]
    return safe_float(item.get("nv")), safe_float(item.get("cr"))


def score_kr(symbol: str, name: str) -> Optional[ScoreRow]:
    if krx_stock is None:
        return None
    try:
        df, end = get_kr_ohlcv_safe(symbol, lookback_days=140)
        if df is None or df.empty or len(df) < 20:
            print(f"[KR skip] {symbol} {name}: 유효한 KRX OHLCV 데이터 없음")
            return None
        close = [safe_float(x) for x in df["종가"].tolist()]
        high = [safe_float(x) for x in df["고가"].tolist()] if "고가" in df.columns else []
        low = [safe_float(x) for x in df["저가"].tolist()] if "저가" in df.columns else []
        volume = [safe_float(x) for x in df["거래량"].tolist()]
        price = close[-1]
        prev = close[-2] if len(close) >= 2 else price
        change_pct = (price - prev) / prev * 100 if prev else 0
        try:
            live_price, live_change_pct = get_kr_current_quote_naver(symbol)
            if live_price > 0:
                price = live_price
                close[-1] = price
                if live_change_pct:
                    change_pct = live_change_pct
                elif prev:
                    change_pct = (price - prev) / prev * 100
        except Exception as exc:
            print(f"[KR live quote fallback] {symbol}: {type(exc).__name__}: {exc}")

        timing_score, rsi14, ma20_gap_pct, timing_bits = calc_timing_score(close, price, change_pct)

        sma20 = statistics.mean(close[-20:])
        sma60 = statistics.mean(close[-60:]) if len(close) >= 60 else statistics.mean(close)

        trend_score = 7
        if price > sma20: trend_score += 6
        if price > sma60: trend_score += 6
        if sma20 > sma60: trend_score += 4
        if len(close) >= 21 and close[-1] > close[-20]: trend_score += 2
        trend_score = int(clamp(trend_score, 0, 25))

        avgv = statistics.mean(volume[-20:]) or 1
        volume_ratio = volume[-1] / avgv
        volume_score = int(clamp(7 + (volume_ratio - 1) * 7, 0, 20))

        news_score = 8
        earnings_score = 8

        foreign_score, institution_score, investor_bits = get_kr_investor_scores(symbol, end)
        investor_bonus = foreign_score + institution_score

        flow_score = int(clamp(6 + max(0, change_pct) * 0.8 + max(0, volume_ratio - 1) * 1.8 + investor_bonus * 0.55, 0, 15))
        risk_score = int(clamp(8 - max(0, ma20_gap_pct - 18) * 0.2 - max(0, -change_pct - 5) * 0.4, 0, 10))
        theme_score = KR_THEME_BOOST.get(symbol, 0)

        old_component_sum = trend_score + volume_score + news_score + earnings_score + flow_score + risk_score
        total = int(clamp(old_component_sum * 0.75 + timing_score + theme_score + investor_bonus * 0.45, 0, 100))

        bits: List[str] = []
        if trend_score >= 20: bits.append("추세 강함")
        if volume_score >= 15: bits.append("거래량 증가")
        if flow_score >= 11: bits.append("수급 관심 후보")
        if theme_score >= 5: bits.append("핵심 테마")
        bits.extend(investor_bits)
        bits.extend(timing_bits)
        if not bits: bits.append("대형주 관찰 대상")

        grade = get_grade(total)
        entry, stop, target = make_trade_plan(price, total, close, high, low)
        meta = plan_meta(price, entry, stop, target)
        confidence = confidence_grade_from_scores(
            [trend_score, volume_score, news_score, earnings_score, flow_score, timing_score],
            total, timing_score, risk_score
        )
        success_prob = int(clamp(36 + total * 0.34 + timing_score * 0.65 + investor_bonus * 0.5 + min(meta["rr"], 3) * 3 - max(0, change_pct - 6) * 2, 35, 84))
        bits.append(f"성공확률 {success_prob}% 추정")
        reason = " + ".join(bits[:5])
        return ScoreRow(
            symbol=symbol, name=name, market="KR", score=total, grade=grade,
            price=round(price, 0), entry_price=round(entry, 0), stop_price=round(stop, 0), target_price=round(target, 0),
            change_text=f"{change_pct:+.1f}%", reason=reason, beginner_note=make_note(total, grade, reason),
            decision=make_decision(total), risk_level=make_risk_level(total), action_text=make_dynamic_action(total, entry, stop, target),
            trend_score=trend_score, volume_score=volume_score, news_score=news_score, earnings_score=earnings_score,
            flow_score=flow_score, risk_score=risk_score, timing_score=timing_score, theme_score=theme_score,
            confidence_grade=confidence, rsi14=rsi14, ma20_gap_pct=ma20_gap_pct, final_score=total,
            foreign_score=foreign_score, institution_score=institution_score,
            asset_class="STOCK", trade_type="STOCK_SWING", side="LONG", leverage=1,
        )
    except Exception as e:
        print(f"[KR skip] {symbol} {name}: {e}")
        return None


def estimate_probability_fields(row: ScoreRow) -> None:
    """
    v5.1: 승률 우선 엔진.
    raw score가 높아도 과열/위험/타이밍 불량이면 final_score를 강하게 낮춥니다.
    아직 실제 장기 백테스트 DB가 없으므로 초기값은 보수적 휴리스틱이고,
    모의투자/성과 기록이 쌓이면 win_rate를 실제 승률로 교체하는 구조입니다.
    """
    raw_score = row.score
    confidence_bonus = {"A+": 5, "A": 3, "B": 0, "C": -3}.get(row.confidence_grade, 0)
    change_pct = parse_change_pct(row.change_text)
    is_short = row.asset_class == "FUTURES" and row.side == "SHORT"
    meta = plan_meta(row.price, row.entry_price, row.stop_price, row.target_price, row.side)
    chase_gap_pct = 0.0
    if row.entry_price > 0:
        if is_short:
            chase_gap_pct = max(0.0, (row.entry_price - row.price) / row.entry_price * 100)
        else:
            chase_gap_pct = max(0.0, (row.price - row.entry_price) / row.entry_price * 100)

    # 손익비가 나쁜 종목은 원점수가 높아도 최종 랭킹에서 밀립니다.
    if meta["rr"] < 1.30:
        rr_penalty = 16
    elif meta["rr"] < 1.50:
        rr_penalty = 9
    elif meta["rr"] < 1.70:
        rr_penalty = 4
    else:
        rr_penalty = 0

    # LONG은 과열/급등, SHORT는 과매도/급락 추격을 같은 강도로 경계합니다.
    overheat_penalty = 0
    timing_quality_bonus = 0
    if is_short:
        if row.rsi14 <= 20: overheat_penalty += 18
        elif row.rsi14 <= 25: overheat_penalty += 12
        elif row.rsi14 <= 32: overheat_penalty += 6
        if row.ma20_gap_pct <= -18: overheat_penalty += 16
        elif row.ma20_gap_pct <= -12: overheat_penalty += 10
        elif row.ma20_gap_pct <= -8: overheat_penalty += 5
        if change_pct <= -7: overheat_penalty += 8
        elif change_pct <= -5: overheat_penalty += 4
        if chase_gap_pct >= 6: overheat_penalty += 14
        elif chase_gap_pct >= 4: overheat_penalty += 9
        elif chase_gap_pct >= 2.5: overheat_penalty += 5
        if 35 <= row.rsi14 <= 58 and -6 <= row.ma20_gap_pct <= 2:
            timing_quality_bonus = 5
    else:
        if row.rsi14 >= 82: overheat_penalty += 20
        elif row.rsi14 >= 75: overheat_penalty += 14
        elif row.rsi14 >= 68: overheat_penalty += 6
        if row.ma20_gap_pct >= 20: overheat_penalty += 18
        elif row.ma20_gap_pct >= 15: overheat_penalty += 11
        elif row.ma20_gap_pct >= 9: overheat_penalty += 5
        if change_pct >= 10: overheat_penalty += 12
        elif change_pct >= 7: overheat_penalty += 8
        elif change_pct >= 5: overheat_penalty += 3
        if chase_gap_pct >= 6: overheat_penalty += 14
        elif chase_gap_pct >= 4: overheat_penalty += 9
        elif chase_gap_pct >= 2.5: overheat_penalty += 5
        if 42 <= row.rsi14 <= 65 and -3 <= row.ma20_gap_pct <= 6:
            timing_quality_bonus = 6

    # 동일한 기술적 품질이라면 변동성이 큰 자산이 주식보다 낙관적으로 보이지 않게 보정합니다.
    market_adjustment = {"US": 1.0, "KR": 0.0, "CRYPTO": -2.0, "FUTURES": -3.0}.get(row.market, 0.0)

    loss_risk = int(clamp(
        16
        + max(0, 10 - row.risk_score) * 4.5
        + max(0, meta["loss_pct"] - 9) * 1.25
        + rr_penalty * 0.9
        + overheat_penalty * 0.65
        + chase_gap_pct * 1.15
        - min(row.timing_score, 20) * 0.45
        - timing_quality_bonus * 0.5,
        5, 96
    ))

    # raw score는 기반 품질로만 쓰고 실제 진입 확률은 timing/risk/RR에 더 크게 반응합니다.
    win_rate = clamp(
        30
        + raw_score * 0.17
        + row.timing_score * 0.90
        + row.risk_score * 0.60
        + confidence_bonus
        + timing_quality_bonus
        + max(0, row.flow_score - 8) * 0.35
        + min(meta["rr"], 2.5) * 1.8
        - overheat_penalty * 0.72
        - chase_gap_pct * 0.80
        - rr_penalty * 0.45
        - max(0, loss_risk - 55) * 0.18
        + market_adjustment,
        30, 88
    )

    # 기대수익은 목표/손절폭과 승률을 직접 결합한 보수적 기대값입니다.
    probability = win_rate / 100.0
    expected_value = probability * meta["gain_pct"] - (1 - probability) * meta["loss_pct"]
    expected = clamp(expected_value * 0.72 - overheat_penalty * 0.08 - chase_gap_pct * 0.12, -10, 20)

    final_score = int(clamp(
        raw_score * 0.20
        + win_rate * 0.45
        + row.timing_score * 1.00
        + (100 - loss_risk) * 0.10
        + expected * 0.70
        + min(meta["rr"], 2.5) * 1.8
        + timing_quality_bonus * 0.65
        - overheat_penalty * 0.60
        - chase_gap_pct * 1.35
        - rr_penalty * 0.35
        + market_adjustment,
        0, 100
    ))

    row.final_score = final_score
    row.score = final_score
    row.grade = get_grade(row.score)
    row.win_rate = round(float(win_rate), 1)
    row.expected_return = round(float(expected), 1)
    row.loss_risk_score = loss_risk
    if row.final_score >= 86 and row.timing_score >= 14 and loss_risk <= 42:
        row.confidence_grade = "A+"
    elif row.final_score >= 76 and row.timing_score >= 11 and loss_risk <= 56:
        row.confidence_grade = "A"
    elif row.final_score >= 64 and loss_risk <= 68:
        row.confidence_grade = "B"
    else:
        row.confidence_grade = "C"

    if row.win_rate >= 68 and row.expected_return >= 4.0 and row.timing_score >= 13 and loss_risk <= 52 and overheat_penalty < 8 and chase_gap_pct < 2.5:
        row.paper_signal = "확률우위"
    elif row.win_rate >= 60 and row.expected_return >= 1.5 and row.timing_score >= 10 and loss_risk <= 64 and overheat_penalty < 12 and chase_gap_pct < 4:
        row.paper_signal = "관찰매수"
    elif loss_risk >= 72 or overheat_penalty >= 12 or chase_gap_pct >= 4:
        row.paper_signal = "과열주의"
    else:
        row.paper_signal = "관찰"

    if row.paper_signal == "확률우위":
        row.decision = "1차 분할매수"
    elif row.paper_signal == "관찰매수":
        row.decision = "진입가 대기"
    elif row.paper_signal == "과열주의":
        row.decision = "추격금지"
    else:
        row.decision = "관망"

    if loss_risk <= 35: row.risk_level = "낮음"
    elif loss_risk <= 55: row.risk_level = "보통"
    elif loss_risk <= 70: row.risk_level = "높음"
    else: row.risk_level = "매우높음"

    reason_parts = [
        part.strip() for part in row.reason.split("+")
        if part.strip() and "성공확률" not in part and "원점수" not in part and "승률" not in part
    ][:4]
    reason_parts.extend([
        f"진입확률 {row.win_rate:.1f}%",
        f"기대수익 {row.expected_return:+.1f}%",
        f"손익비 {meta['rr']:.2f}:1",
    ])
    row.reason = " + ".join(reason_parts)
    practical_note = (
        "추격매수 금지, 1차 진입가 근처 대기. "
        if not is_short else "급락 추격 숏 금지, 1차 진입가 근처 반등 대기. "
    )
    row.beginner_note = (
        f"{row.grade} Grade / {row.paper_signal}. {practical_note}"
        f"거래량 유지 확인 후 분할 접근하고 손절가 이탈 시 관망하세요. "
        f"예상 손익비 {meta['rr']:.2f}:1, 손실위험 {loss_risk}/100."
    )
    row.action_text = (
        f"{make_dynamic_action(row.final_score, row.entry_price, row.stop_price, row.target_price, row.side)} "
        f"신호 {row.paper_signal}, 추정승률 {row.win_rate:.1f}%, "
        f"기대수익 {row.expected_return:+.1f}%, 손실위험 {row.loss_risk_score}/100. "
        f"거래량 유지 확인, 손절가 이탈 시 관망."
    )


def enrich_probability_rows(rows: List[ScoreRow]) -> None:
    for row in rows:
        estimate_probability_fields(row)


def market_bucket(row: ScoreRow) -> str:
    asset = str(getattr(row, "asset_class", "")).upper()
    market = str(getattr(row, "market", "")).upper()
    if asset == "FUTURES" or market == "FUTURES":
        return "FUTURES"
    if asset == "CRYPTO" or market in ("CRYPTO", "COIN"):
        return "CRYPTO"
    if market == "KR":
        return "KR"
    return "US"


def market_counts(rows: List[ScoreRow]) -> Dict[str, int]:
    counts = {"US": 0, "KR": 0, "CRYPTO": 0, "FUTURES": 0}
    for row in rows:
        counts[market_bucket(row)] += 1
    return counts


def print_market_top10(rows: List[ScoreRow]) -> None:
    print("\n=== 시장별 TOP10 미리보기 (final_score 기준) ===")
    for bucket in ("US", "KR", "CRYPTO", "FUTURES"):
        part = sorted(
            (row for row in rows if market_bucket(row) == bucket),
            key=lambda row: (row.final_score, row.win_rate, row.expected_return, row.timing_score),
            reverse=True,
        )[:10]
        print(f"\n[{bucket} TOP10] 후보 {sum(1 for row in rows if market_bucket(row) == bucket)}개")
        if not part:
            print("  - 후보 없음")
            continue
        for rank, row in enumerate(part, 1):
            print(
                f"  {rank:2}. {row.name}({row.symbol}) final {row.final_score:3} / "
                f"승률 {row.win_rate:4.1f}% / 기대 {row.expected_return:+5.1f}% / "
                f"위험 {row.loss_risk_score:2}/100 / timing {row.timing_score:2}/20 / {row.paper_signal}"
            )


def get_supabase_client():
    load_dotenv()
    if create_client is None:
        raise RuntimeError("supabase 패키지가 설치되지 않았습니다. pip install -r requirements.txt 실행 필요")
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        raise RuntimeError("SUPABASE_URL 또는 SUPABASE_SERVICE_ROLE_KEY가 없습니다. engine/.env에 넣으세요.")
    return create_client(url, key)


def _data_from_response(resp: Any) -> List[Dict[str, Any]]:
    data = getattr(resp, "data", None)
    if data is None and isinstance(resp, dict):
        data = resp.get("data")
    return data or []


def update_paper_trading(sb: Any, rows: List[ScoreRow], cfg: Dict[str, Any]) -> None:
    """
    v6.0 모의투자 엔진.
    - 주식 최대 7개, 코인 현물/스윙 최대 5개, 선물 LONG/SHORT 최대 3개
    - 실제 주문은 절대 내지 않고 Supabase에 기록만 합니다.
    - 선물 SHORT는 가격 하락 시 수익으로 계산합니다.
    """
    if not bool(cfg.get("paper_trading_enabled", True)):
        print("모의투자: 비활성화")
        return

    trade_amount = float(cfg.get("paper_trade_amount", 100000))
    max_total = int(cfg.get("paper_max_positions", 15))
    max_by_asset = {
        "STOCK": int(cfg.get("paper_max_stock_positions", 7)),
        "CRYPTO": int(cfg.get("paper_max_crypto_positions", 5)),
        "FUTURES": int(cfg.get("paper_max_futures_positions", 3)),
    }
    min_score = int(cfg.get("paper_min_score", 75))
    min_timing = int(cfg.get("paper_min_timing", 8))
    now_iso = datetime.now(KST).isoformat()
    row_by_symbol = {r.symbol: r for r in rows}

    try:
        open_resp = sb.table("paper_positions").select("*").eq("status", "OPEN").execute()
        open_positions = _data_from_response(open_resp)
    except Exception as e:
        print("[WARN] 모의투자 테이블 조회 실패. paper SQL을 먼저 실행하세요:", e)
        return

    # 1) 기존 오픈 포지션 평가/청산
    for pos in open_positions:
        sym = pos.get("symbol")
        row = row_by_symbol.get(sym)
        if not row:
            continue
        entry = safe_float(pos.get("entry_price"))
        qty = safe_float(pos.get("qty"))
        current = row.price
        side = str(pos.get("side") or row.side or "LONG").upper()
        if side == "SHORT":
            pnl = (entry - current) * qty
            pnl_pct = ((entry - current) / entry * 100) if entry > 0 else 0.0
        else:
            pnl = (current - entry) * qty
            pnl_pct = ((current - entry) / entry * 100) if entry > 0 else 0.0

        exit_reason = ""
        if side == "SHORT":
            if current >= safe_float(pos.get("stop_price")):
                exit_reason = "선물 숏 손절가 도달"
            elif current <= safe_float(pos.get("target_price")):
                exit_reason = "선물 숏 목표가 도달"
        else:
            if current <= safe_float(pos.get("stop_price")):
                exit_reason = "손절가 도달"
            elif current >= safe_float(pos.get("target_price")):
                exit_reason = "목표가 도달"
        if not exit_reason:
            if row.score < 58:
                exit_reason = "점수 붕괴"
            elif row.loss_risk_score >= 84 and pnl_pct < 1:
                exit_reason = "손실위험 급등"

        common_update = {
            "current_price": current, "pnl": round(pnl, 2), "pnl_pct": round(pnl_pct, 2),
            "last_seen_at": now_iso, "score": row.score, "timing_score": row.timing_score,
            "win_rate": row.win_rate, "expected_return": row.expected_return,
            "loss_risk_score": row.loss_risk_score,
        }
        if exit_reason:
            common_update.update({"status": "CLOSED", "exit_price": current, "closed_at": now_iso, "exit_reason": exit_reason})
            sb.table("paper_positions").update(common_update).eq("id", pos.get("id")).execute()
            sb.table("paper_trades").insert({
                "symbol": row.symbol, "name": row.name, "market": row.market, "asset_class": row.asset_class,
                "trade_type": row.trade_type, "side": "CLOSE_" + side,
                "price": current, "qty": qty, "amount": round(current * qty, 2),
                "reason": exit_reason, "score": row.score, "timing_score": row.timing_score,
                "win_rate": row.win_rate, "expected_return": row.expected_return,
                "pnl": round(pnl, 2), "pnl_pct": round(pnl_pct, 2), "created_at": now_iso,
            }).execute()
            print(f"모의투자 청산: {row.name}({row.symbol}) {exit_reason} 손익 {pnl_pct:+.2f}%")
        else:
            sb.table("paper_positions").update(common_update).eq("id", pos.get("id")).execute()

    # 2) 클래스별 슬롯 계산
    try:
        open_resp = sb.table("paper_positions").select("symbol, asset_class").eq("status", "OPEN").execute()
        open_now = _data_from_response(open_resp)
    except Exception:
        open_now = open_positions
    open_symbols = {p.get("symbol") for p in open_now}
    total_slots = max(0, max_total - len(open_symbols))
    open_count_by_asset = {"STOCK": 0, "CRYPTO": 0, "FUTURES": 0}
    for p in open_now:
        ac = str(p.get("asset_class") or ("CRYPTO" if p.get("market") == "CRYPTO" else "FUTURES" if p.get("market") == "FUTURES" else "STOCK")).upper()
        if ac in open_count_by_asset:
            open_count_by_asset[ac] += 1

    candidates: List[ScoreRow] = []
    for ac, limit in max_by_asset.items():
        ac_rows = [r for r in rows if r.asset_class == ac]
        ac_rows.sort(key=lambda x: (x.score, x.win_rate, x.expected_return, x.timing_score), reverse=True)
        slots = max(0, limit - open_count_by_asset.get(ac, 0))
        candidates.extend(ac_rows[:slots])
    candidates.sort(key=lambda x: (x.score, x.win_rate, x.expected_return, x.timing_score), reverse=True)

    for row in candidates:
        if total_slots <= 0:
            break
        if row.symbol in open_symbols:
            continue
        if row.score < min_score or row.timing_score < min_timing:
            continue
        if row.loss_risk_score >= 74 or row.paper_signal == "과열주의":
            continue
        qty = trade_amount / row.price if row.price > 0 else 0
        if qty <= 0:
            continue
        payload = {
            "symbol": row.symbol, "name": row.name, "market": row.market, "asset_class": row.asset_class,
            "trade_type": row.trade_type, "side": row.side, "leverage": row.leverage,
            "status": "OPEN", "entry_price": row.price, "current_price": row.price,
            "qty": qty, "amount": trade_amount, "score": row.score, "timing_score": row.timing_score,
            "confidence_grade": row.confidence_grade, "win_rate": row.win_rate,
            "expected_return": row.expected_return, "loss_risk_score": row.loss_risk_score,
            "entry_reason": row.reason, "stop_price": row.stop_price, "target_price": row.target_price,
            "opened_at": now_iso, "last_seen_at": now_iso, "pnl": 0, "pnl_pct": 0,
        }
        sb.table("paper_positions").insert(payload).execute()
        sb.table("paper_trades").insert({
            "symbol": row.symbol, "name": row.name, "market": row.market, "asset_class": row.asset_class,
            "trade_type": row.trade_type, "side": row.side, "price": row.price, "qty": qty,
            "amount": trade_amount, "reason": row.reason, "score": row.score,
            "timing_score": row.timing_score, "win_rate": row.win_rate,
            "expected_return": row.expected_return, "pnl": 0, "pnl_pct": 0, "created_at": now_iso,
        }).execute()
        open_symbols.add(row.symbol)
        total_slots -= 1
        print(f"모의투자 매수: {row.name}({row.symbol}) {row.asset_class}/{row.side} {row.price} / 승률 {row.win_rate:.1f}% / 신호 {row.paper_signal}")

    # 3) 포트폴리오 스냅샷
    try:
        all_open = _data_from_response(sb.table("paper_positions").select("*").eq("status", "OPEN").execute())
        all_closed = _data_from_response(sb.table("paper_positions").select("pnl").eq("status", "CLOSED").execute())
        unrealized = sum(safe_float(p.get("pnl")) for p in all_open)
        invested = sum(safe_float(p.get("amount")) for p in all_open)
        realized_total = sum(safe_float(p.get("pnl")) for p in all_closed)
        closed_total = len(all_closed)
        wins_total = sum(1 for p in all_closed if safe_float(p.get("pnl")) > 0)
        win_rate_total = round(wins_total / closed_total * 100, 1) if closed_total else 0.0
        by_asset = {"STOCK": 0.0, "CRYPTO": 0.0, "FUTURES": 0.0}
        for p in all_open:
            ac = str(p.get("asset_class") or "STOCK").upper()
            if ac in by_asset:
                by_asset[ac] += safe_float(p.get("pnl"))
        sb.table("paper_portfolio_snapshots").insert({
            "created_at": now_iso, "open_positions": len(all_open), "closed_trades": closed_total,
            "invested": round(invested, 2), "unrealized_pnl": round(unrealized, 2),
            "realized_pnl": round(realized_total, 2), "total_pnl": round(unrealized + realized_total, 2),
            "win_rate": win_rate_total, "stock_pnl": round(by_asset["STOCK"], 2),
            "crypto_pnl": round(by_asset["CRYPTO"], 2), "futures_pnl": round(by_asset["FUTURES"], 2),
        }).execute()
        print(f"모의투자 현황: 보유 {len(all_open)}개 / 실현손익 {realized_total:+.0f} / 평가손익 {unrealized:+.0f} / 누적승률 {win_rate_total:.1f}%")
    except Exception as e:
        print("[WARN] 모의투자 스냅샷 저장 실패:", e)

HOT_NEWS_POSITIVE_KEYWORDS = [
    "beat", "surge", "rally", "record", "upgrade", "approval", "partnership", "contract",
    "launch", "buyback", "etf inflow", "breakthrough", "호재", "상승", "급등", "수주",
    "승인", "실적 호조", "상향", "계약", "협력", "출시", "매수", "흑자",
]

HOT_NEWS_NEGATIVE_KEYWORDS = [
    "miss", "plunge", "drop", "crash", "downgrade", "lawsuit", "probe", "ban", "recall",
    "hack", "outflow", "selloff", "악재", "하락", "급락", "소송", "조사", "규제",
    "금지", "리콜", "해킹", "유출", "매도", "적자", "실적 부진",
]


def _rss_text(node: ET.Element, name: str) -> str:
    found = node.find(name)
    return html.unescape((found.text or "").strip()) if found is not None else ""


def _parse_rss_datetime(raw: str) -> datetime:
    if not raw:
        return datetime.now(timezone.utc)
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return datetime.now(timezone.utc)


def _clean_news_summary(text: str, max_len: int = 420) -> str:
    text = html.unescape(str(text or ""))
    for token in ("<p>", "</p>", "<br>", "<br/>", "<br />", "<b>", "</b>"):
        text = text.replace(token, " ")
    text = " ".join(text.split())
    return text[:max_len] + ("..." if len(text) > max_len else "")


def _hot_news_sources() -> List[tuple[str, str]]:
    queries = [
        ("Google KR 시장", "코스피 반도체 2차전지 로봇 AI 원전 방산 주식"),
        ("Google US 시장", "AI semiconductor stocks crypto bitcoin ETF market movers"),
        ("Google Crypto", "bitcoin ethereum solana xrp crypto ETF regulation"),
    ]
    urls = [
        (name, f"https://news.google.com/rss/search?q={quote_plus(q)}&hl=ko&gl=KR&ceid=KR:ko")
        for name, q in queries
    ]
    urls.extend([
        ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
        ("Cointelegraph", "https://cointelegraph.com/rss"),
    ])
    return urls


def _row_aliases(row: ScoreRow) -> List[str]:
    symbol = str(row.symbol or "").upper().strip()
    base = symbol.replace("-LONG", "").replace("-SHORT", "")
    aliases = {symbol, base, str(row.name or "").strip()}
    if base.endswith("USDT"):
        aliases.add(base[:-4])
    if "." in base:
        aliases.add(base.split(".")[0])
    return [a for a in aliases if len(a) >= 2]


def _score_news_sentiment(text: str) -> tuple[str, List[str]]:
    lower = text.lower()
    pos = [kw for kw in HOT_NEWS_POSITIVE_KEYWORDS if kw.lower() in lower]
    neg = [kw for kw in HOT_NEWS_NEGATIVE_KEYWORDS if kw.lower() in lower]
    if len(pos) > len(neg):
        return "positive", pos[:8]
    if len(neg) > len(pos):
        return "negative", neg[:8]
    return "neutral", (pos + neg)[:8]


def collect_hot_news(rows: List[ScoreRow], cfg: Dict[str, Any]) -> List[HotNewsItem]:
    if not cfg.get("hot_news_enabled", True):
        return []

    timeout = float(cfg.get("hot_news_fetch_timeout", 4.0))
    lookback_minutes = int(cfg.get("hot_news_lookback_minutes", 720))
    max_items = int(cfg.get("hot_news_max_items", 40))
    now = datetime.now(timezone.utc)
    recent_rows = sorted(rows, key=lambda r: (r.score, r.win_rate, r.expected_return), reverse=True)[:160]
    alias_map: List[tuple[ScoreRow, List[str]]] = [(r, _row_aliases(r)) for r in recent_rows]
    seen_urls: set[str] = set()
    items: List[HotNewsItem] = []

    def fetch_source(source: str, url: str) -> List[Dict[str, Any]]:
        try:
            res = requests.get(url, timeout=timeout, headers={"User-Agent": "AlphaRadarHotNews/1.0"})
            res.raise_for_status()
            root = ET.fromstring(res.content)
            out = []
            for item in root.findall(".//item")[:30]:
                title = _rss_text(item, "title")
                link = _rss_text(item, "link")
                summary = _clean_news_summary(_rss_text(item, "description"))
                published = _parse_rss_datetime(_rss_text(item, "pubDate"))
                out.append({"source": source, "title": title, "url": link, "summary": summary, "published": published})
            return out
        except Exception as exc:
            print(f"[HOT NEWS skip] {source}: {type(exc).__name__}: {exc}", flush=True)
            return []

    feed_rows: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=5, thread_name_prefix="alpha-news") as pool:
        futures = [pool.submit(fetch_source, source, url) for source, url in _hot_news_sources()]
        for future in as_completed(futures):
            feed_rows.extend(future.result())

    for news in feed_rows:
        url = news.get("url") or ""
        if not url or url in seen_urls:
            continue
        published: datetime = news.get("published") or now
        age_minutes = max(0.0, (now - published.astimezone(timezone.utc)).total_seconds() / 60.0)
        if age_minutes > lookback_minutes:
            continue

        title = str(news.get("title") or "")
        summary = str(news.get("summary") or "")
        haystack = f"{title} {summary}".lower()
        sentiment, matched_keywords = _score_news_sentiment(haystack)

        matched_rows: List[ScoreRow] = []
        matched_aliases: List[str] = []
        for row, aliases in alias_map:
            for alias in aliases:
                low_alias = alias.lower()
                if len(low_alias) >= 2 and low_alias in haystack:
                    matched_rows.append(row)
                    matched_aliases.append(alias)
                    break
            if len(matched_rows) >= 5:
                break
        if not matched_rows:
            continue

        primary = matched_rows[0]
        recency_score = max(0, int(45 - age_minutes / 12))
        sentiment_bonus = 18 if sentiment in ("positive", "negative") else 6
        rank_bonus = max(0, int(primary.score / 5))
        hot_score = int(clamp(recency_score + sentiment_bonus + rank_bonus + len(matched_rows) * 4, 0, 100))
        seen_urls.add(url)
        items.append(HotNewsItem(
            symbol=primary.symbol,
            name=primary.name,
            market=primary.market,
            title=title[:260],
            summary=summary or title,
            url=url,
            source=str(news.get("source") or "RSS"),
            published_at=published.astimezone(KST).isoformat(),
            sentiment=sentiment,
            hot_score=hot_score,
            matched_keywords=", ".join(dict.fromkeys(matched_keywords + matched_aliases[:6])),
            related_symbols=", ".join(dict.fromkeys([r.symbol for r in matched_rows])),
        ))

    items.sort(key=lambda x: (x.hot_score, x.published_at), reverse=True)
    if items:
        print(f"[HOT NEWS] {len(items[:max_items])}개 수집/매칭 완료", flush=True)
    return items[:max_items]


def hot_news_to_alerts(items: List[HotNewsItem], cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    threshold = int(cfg.get("hot_news_alert_score", 78))
    alerts: List[Dict[str, Any]] = []
    for item in items:
        if item.hot_score < threshold:
            continue
        if item.sentiment == "positive":
            level = "news_good"
            prefix = "호재 뉴스"
        elif item.sentiment == "negative":
            level = "news_bad"
            prefix = "악재 뉴스"
        else:
            level = "news_info"
            prefix = "핫뉴스"
        alerts.append({
            "symbol": item.symbol,
            "title": f"{prefix}: {item.name} / {item.hot_score}점",
            "message": f"{item.title}\n\n{item.summary}\n\n출처: {item.source}\n원문: {item.url}",
            "level": level,
        })
    return alerts[:12]


def upload_to_supabase(rows: List[ScoreRow], alerts: List[Dict[str, Any]], hot_news: Optional[List[HotNewsItem]] = None) -> None:
    print("Supabase 업로드 시작")
    counts = market_counts(rows)
    min_stock_rows = int(os.getenv("ALPHA_RADAR_MIN_STOCK_ROWS", "20"))
    missing = [market for market in ("US", "KR") if counts[market] < min_stock_rows]
    if missing:
        detail = ", ".join(f"{market} {counts[market]}개" for market in missing)
        raise RuntimeError(
            f"[UPLOAD SAFETY] {detail}: 최소 {min_stock_rows}개 미달. "
            "기존 rankings 보호를 위해 삭제/업로드를 중단합니다."
        )

    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    print("SUPABASE_URL 있음:", bool(url))
    print("SUPABASE_SERVICE_ROLE_KEY 있음:", bool(key))
    sb = get_supabase_client()
    print("rankings 기존 데이터 삭제 시작")
    sb.table("rankings").delete().neq("id", 0).execute()
    print("rankings 기존 데이터 삭제 완료")

    payload = [r.__dict__ for r in rows]
    print("rankings 업로드 대상:", len(payload))
    if payload:
        try:
            sb.table("rankings").insert(payload).execute()
            print(f"rankings insert 성공: {len(payload)}개")
        except Exception as e:
            # Supabase에 v5 컬럼을 아직 추가하지 않은 경우에도 기존 화면은 죽지 않게 레거시 컬럼만 재시도
            print("[WARN] v5.x 컬럼 insert 실패. Supabase SQL 업그레이드를 먼저 실행하세요.")
            print("[WARN] 오류:", e)
            legacy_keys = {
                "symbol", "name", "market", "score", "grade", "price", "entry_price", "stop_price", "target_price",
                "change_text", "reason", "beginner_note", "decision", "risk_level", "action_text",
                "trend_score", "volume_score", "news_score", "earnings_score", "flow_score", "risk_score",
            }
            legacy_payload = [{k: v for k, v in item.items() if k in legacy_keys} for item in payload]
            sb.table("rankings").insert(legacy_payload).execute()
            print(f"rankings legacy insert 성공: {len(legacy_payload)}개")

    print("alerts 업로드 대상:", len(alerts))
    if alerts:
        sb.table("alerts").insert(alerts).execute()
        print(f"alerts insert 성공: {len(alerts)}개")
    if hot_news:
        try:
            news_payload = [n.__dict__ for n in hot_news]
            sb.table("hot_news").delete().neq("id", 0).execute()
            sb.table("hot_news").insert(news_payload).execute()
            print(f"hot_news insert 성공: {len(news_payload)}개")
        except Exception as e:
            print("[WARN] hot_news 테이블 업로드 실패. sql/schema_live.sql의 hot_news 마이그레이션을 먼저 적용하세요.")
            print("[WARN] hot_news 오류:", e)
    print(
        "시장별 rankings 업로드 완료: "
        f"US {counts['US']} / KR {counts['KR']} / "
        f"CRYPTO {counts['CRYPTO']} / FUTURES {counts['FUTURES']}"
    )
    print("Supabase 업로드 끝")


def ranking_live_price(row: Dict[str, Any]) -> tuple[float, str]:
    market = str(row.get("market") or "").upper()
    symbol = str(row.get("symbol") or "").upper().strip()
    side = str(row.get("side") or "").upper().strip()
    base_symbol = symbol
    if base_symbol.endswith("-LONG"):
        base_symbol = base_symbol[:-5]
        side = side or "LONG"
    elif base_symbol.endswith("-SHORT"):
        base_symbol = base_symbol[:-6]
        side = side or "SHORT"

    if (market == "FUTURES" or side in ("LONG", "SHORT")) and base_symbol.endswith("USDT"):
        return binance_current_price(base_symbol, futures=True), ""
    if market in ("CRYPTO", "COIN") or base_symbol.endswith("USDT"):
        return binance_current_price(base_symbol, futures=False), ""
    if market == "KR" or base_symbol.isdigit():
        price, change_pct = get_kr_current_quote_naver(base_symbol)
        return price, f"{change_pct:+.1f}%" if change_pct else ""
    return 0.0, ""


def quick_update_ranking_prices(sb=None, limit: int = 80) -> int:
    """풀스캔 사이에 화면용 현재가만 빠르게 갱신합니다."""
    if sb is None:
        sb = get_supabase_client()
    rows = _data_from_response(
        sb.table("rankings").select("id,symbol,market,side").order("score", desc=True).limit(limit).execute()
    )

    def update_one(row: Dict[str, Any]) -> bool:
        try:
            price, change_text = ranking_live_price(row)
            if price <= 0:
                return False
            payload = {"price": round(price, 6)}
            if change_text:
                payload["change_text"] = change_text
            row_id = row.get("id")
            if row_id is not None:
                sb.table("rankings").update(payload).eq("id", row_id).execute()
                return True
        except Exception as exc:
            print(f"[PRICE UPDATE skip] {row.get('symbol')}: {type(exc).__name__}: {exc}", flush=True)
        return False

    updated = 0
    workers = max(2, min(12, int(os.getenv("ALPHA_RADAR_PRICE_UPDATE_WORKERS", "8"))))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="alpha-price") as pool:
        futures = [pool.submit(update_one, row) for row in rows]
        for future in as_completed(futures):
            if future.result():
                updated += 1
    if updated:
        print(f"[PRICE UPDATE] rankings 현재가 {updated}개 갱신", flush=True)
    return updated

def apply_top7_market_balance(rows: List[ScoreRow]) -> List[ScoreRow]:
    # v5.1: 미국/한국 강제 비율 없음. 확률점수(score=final_score) 순 TOP7.
    if not rows:
        return rows
    print(f"스캔 성공: 전체 {len(rows)}개 / US {sum(1 for r in rows if r.market == 'US')}개 / KR {sum(1 for r in rows if r.market == 'KR')}개 / CRYPTO {sum(1 for r in rows if r.market == 'CRYPTO')}개 / FUTURES {sum(1 for r in rows if r.market == 'FUTURES')}개")
    rows.sort(key=lambda x: (x.score, x.win_rate, x.expected_return, x.timing_score), reverse=True)
    return rows


def scan_us_universe(max_price: float) -> List[ScoreRow]:
    """확장 US 유니버스를 제한된 동시성으로 스캔합니다."""
    found: List[ScoreRow] = []
    workers = max(1, int(os.getenv("ALPHA_RADAR_US_WORKERS", "4")))
    print(f"[US scan] {len(US_WATCHLIST)}개 / workers={workers}", flush=True)
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="alpha-us") as pool:
        futures = {
            pool.submit(score_us, sym, name, max_price): (sym, name)
            for sym, name in US_WATCHLIST
        }
        for future in as_completed(futures):
            sym, _ = futures[future]
            try:
                row = future.result()
                if row:
                    found.append(row)
                    print(f"US {sym:6} {row.score:3}점 {row.grade:>2} 타이밍 {row.timing_score:2}/20 신뢰 {row.confidence_grade:>2} {row.change_text:>7} {row.reason}", flush=True)
            except Exception as exc:
                print(f"[US skip] {sym}: {exc}", flush=True)
    return found


def scan_kr_universe() -> List[ScoreRow]:
    """확장 KR 유니버스를 제한된 동시성으로 스캔합니다."""
    found: List[ScoreRow] = []
    # pykrx/KRX는 병렬 요청 시 지연과 빈 응답이 크게 늘어납니다. KR 내부는
    # 직렬 처리하고, US 시장과 시장 단위로만 동시에 실행하는 편이 더 빠르고 안정적입니다.
    workers = max(1, int(os.getenv("ALPHA_RADAR_KR_WORKERS", "8")))
    print(f"[KR scan] {len(KR_WATCHLIST)}개 / workers={workers}", flush=True)
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="alpha-kr") as pool:
        futures = {
            pool.submit(score_kr, sym, name): (sym, name)
            for sym, name in KR_WATCHLIST
        }
        for future in as_completed(futures):
            sym, _ = futures[future]
            try:
                row = future.result()
                if row:
                    found.append(row)
                    print(f"KR {sym:6} {row.score:3}점 {row.grade:>2} 타이밍 {row.timing_score:2}/20 신뢰 {row.confidence_grade:>2} {row.change_text:>7} {row.reason}", flush=True)
            except Exception as exc:
                print(f"[KR skip] {sym}: {exc}", flush=True)
    return found

def run_once() -> None:
    cfg = read_config()
    max_price = float(cfg.get("max_share_price_usd", 1000))
    markets = set(cfg.get("markets", ["US", "KR"]))
    rows: List[ScoreRow] = []
    print("\n=== Alpha Radar AI Engine v7.3 Expanded US/KR Universe scan start ===", flush=True)

    stock_jobs = {}
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="alpha-market") as market_pool:
        if "US" in markets:
            stock_jobs[market_pool.submit(scan_us_universe, max_price)] = "US"
        if "KR" in markets:
            stock_jobs[market_pool.submit(scan_kr_universe)] = "KR"
        for future in as_completed(stock_jobs):
            market = stock_jobs[future]
            try:
                market_rows = future.result()
                rows.extend(market_rows)
                print(f"[{market} scan complete] {len(market_rows)}개", flush=True)
            except Exception as exc:
                print(f"[{market} scan failed] {exc}", flush=True)

    if "CRYPTO" in markets:
        for sym, name in CRYPTO_SPOT_WATCHLIST:
            r = score_crypto_spot(sym, name)
            if r:
                rows.append(r)
                print(f"COIN {sym:12} {r.score:3}점 {r.grade:>2} 타이밍 {r.timing_score:2}/20 신뢰 {r.confidence_grade:>2} {r.change_text:>7} {r.reason}")
            time.sleep(0.08)

    if "FUTURES" in markets:
        for sym, name in FUTURES_WATCHLIST:
            for side in ("LONG", "SHORT"):
                r = score_futures_pair(sym, name, side)
                if r:
                    rows.append(r)
                    print(f"FUT {sym:12} {side:5} {r.score:3}점 {r.grade:>2} 타이밍 {r.timing_score:2}/20 신뢰 {r.confidence_grade:>2} {r.change_text:>7} {r.reason}")
                time.sleep(0.05)

    enrich_probability_rows(rows)

    # v7.4: 검색 누락 방지 패치.
    # 화면은 프론트에서 TOP10만 보여주더라도, Supabase rankings에는 더 넓게 저장해야
    # SK하이닉스처럼 점수순 TOP100 밖으로 잠시 밀린 핵심 종목도 검색됩니다.
    rows.sort(key=lambda x: (x.score, x.win_rate, x.expected_return, x.timing_score), reverse=True)

    bucket_limit = int(os.getenv("ALPHA_RADAR_BUCKET_LIMIT", "999"))
    always_keep_symbols = {
        # 한국 대표/인기/사용자 검색 보장 종목
        "000660",  # SK하이닉스
        "005930",  # 삼성전자
        "005380",  # 현대차
        "000270",  # 기아
        "012450",  # 한화에어로스페이스
        "064350",  # 현대로템
        "042660",  # 한화오션
        "329180",  # HD현대중공업
        "009540",  # HD한국조선해양
        "267260",  # HD현대일렉트릭
        "034020",  # 두산에너빌리티
        "298040",  # 효성중공업
        "196170",  # 알테오젠
        "003230",  # 삼양식품
        "352820",  # 하이브
        "259960",  # 크래프톤
        "277810",  # 레인보우로보틱스
        "454910",  # 두산로보틱스
        "489790",  # 한화비전
        # 미국 대표 검색 보장 종목
        "NVDA", "TSLA", "PLTR", "AMD", "AVGO", "AAPL", "MSFT", "AMZN", "GOOGL", "META",
    }

    selected_by_symbol: Dict[str, ScoreRow] = {}
    for bucket in ("US", "KR", "CRYPTO", "FUTURES"):
        part = [r for r in rows if market_bucket(r) == bucket]
        part.sort(key=lambda x: (x.score, x.win_rate, x.expected_return, x.timing_score), reverse=True)

        # 기본은 시장별 넉넉히 저장
        for r in part[:bucket_limit]:
            selected_by_symbol[r.symbol] = r

        # 핵심 종목은 점수가 낮아도 검색용 저장 대상에 강제 포함
        for r in part:
            if str(r.symbol).upper() in always_keep_symbols:
                selected_by_symbol[r.symbol] = r

    rows = list(selected_by_symbol.values())
    rows.sort(key=lambda x: (market_bucket(x), -x.score, -x.win_rate, -x.expected_return))
    alert_score = int(cfg.get("push_alert_score", 90))
    alerts: List[Dict[str, Any]] = []
    for r in rows[:7]:
        if r.score >= alert_score:
            alerts.append({"symbol": r.symbol, "title": f"{r.name} {r.grade}등급 확률점수 {r.score}점", "message": f"{r.reason} / 승률 {r.win_rate:.1f}% / 기대수익 {r.expected_return:+.1f}% / 손실위험 {r.loss_risk_score}/100 / 타이밍 {r.timing_score}/20 / 신뢰 {r.confidence_grade} / 진입가 {r.entry_price} / 목표가 {r.target_price}", "level": "strong"})

    hot_news = collect_hot_news(rows, cfg)
    alerts.extend(hot_news_to_alerts(hot_news, cfg))

    print_market_top10(rows)
    upload_to_supabase(rows, alerts, hot_news)
    try:
        sb = get_supabase_client()
        update_paper_trading(sb, rows, cfg)
    except Exception as e:
        print(f"[PAPER TRADING ERROR] {e}")
    counts = market_counts(rows)
    print(
        f"\n업로드 완료: rankings {len(rows)}개, alerts {len(alerts)}개 / "
        f"US {counts['US']} / KR {counts['KR']} / "
        f"CRYPTO {counts['CRYPTO']} / FUTURES {counts['FUTURES']}"
    )


def main() -> None:
    cfg = read_config()
    interval = int(cfg.get("scan_interval_minutes", 1))
    price_update_seconds = max(5, int(cfg.get("price_update_seconds", 10)))
    price_update_limit = max(50, int(cfg.get("price_update_limit", 300)))
    loop = os.getenv("ALPHA_RADAR_LOOP", "false").lower() == "true"
    while True:
        try:
            run_once()
        except Exception as e:
            print(f"[ENGINE ERROR] {e}")
        if not loop:
            break
        print(f"\n{interval}분 후 재스캔합니다. 그 사이 현재가는 {price_update_seconds}초마다 갱신합니다. 종료하려면 창을 닫으세요.")
        deadline = time.time() + interval * 60
        while time.time() < deadline:
            time.sleep(min(price_update_seconds, max(0.0, deadline - time.time())))
            try:
                quick_update_ranking_prices(limit=price_update_limit)
            except Exception as e:
                print(f"[PRICE UPDATE ERROR] {e}", flush=True)


if __name__ == "__main__":
    main()
