from flask import Flask, render_template, request, jsonify, redirect
from slack_sdk.errors import SlackApiError
from bs4 import BeautifulSoup
import requests
import time
import json
import smtplib
from email.header import Header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

headers={'Content-Type': 'application/json'}

SLACK_URL = 'yout URL'
keyword = ''

# 구글 뉴스 메인 URL
GOOGLE_URL = 'https://news.google.com'

app = Flask(__name__)

@app.route('/')
def main():
    return render_template('main.html')

@app.route('/search', methods=['GET','POST']) # /search 경로로 요청이 들어온 경우, POST 메소드 사용해서 결과를 게시
def search(): # 검색 기능
    keyword = request.form['keyword'] # main.html에서 form 데이터 중 name이 keyword인 데이터를 가져옴
    limit = int(request.form['limit'])
    results = [] # 결과가 저장될 빈 리스트, 딕셔너리 형태의 result들이 저장될 리스트
    url = GOOGLE_URL + '/search?q=' + keyword + '&hl=ko&gl=KR&ceid=KR%3Ako' # 구글 키워드 검색 주소: news.google.com/rss/search?q=(검색어)&hl=ko&gl=KR&ceid=KR%3Ako
    response = requests.get(url) # 제작된 url로부터 HTML문서를 가져와 response에 저장
    soup = BeautifulSoup(response.content, 'html.parser') # response의 HTML문서를 가져와 파싱
    articles = soup.find_all('div', {'class': 'NiLAwe'}) # div 태그이면서 NiLAwe 클래스인 모든 요소를 찾고, 리스트 형태로 articles에 저장
    
    for article in articles: 
        if keyword in article.h3.a.text: # 구글 뉴스 페이지를 개발자 도구로 확인하면 뉴스 제목들이 NilAwe 클래스 아래 <h3>, <a> 태그 아래에 위치한 것을 확인 가능
            result = {} # 순서번호, 제목, 링크, 체크 여부 등이 저장되어야 하므로 딕셔너리 형태로 선언
            result['title'] = article.h3.a.text # 뉴스 제목
            result['link'] = GOOGLE_URL + article.h3.a['href']#[1:] # a태그에 대해 ['href']를 이용해 링크 추출, 추출된 링크 앞에 .이 있으므로 [1:]로 제거(큰 의미 없음, 하지 않아도 정상 작동되는 것 확인)
            results.append(result) # result 딕셔너리를 results 리스트에 추가
            if len(results) >= limit:
                break
            time.sleep(0.5) # 차단 방지용
    for idx, result in enumerate(results): # 검색 결과가 여러개면 순서번호가 중첩되서 증가해서 아래로 분리
        result['id'] = idx + 1 # 순서번호
    return render_template('search.html', keyword=keyword, results=results)
    # search.html 파일을 렌더링하여 보여줌, keyword와 results 파라미터를 전달
    
@app.route('/send', methods=['POST','GET']) # /send 경로로 요청이 들어온 경우, POST 메소드 사용해서 결과를 게시
def send_slack(): # 슬랙 전송 기능
    # 메시지 전송
    selected = request.form.getlist('selected[]') # search.html에서 form 데이터 중 name이 selected[]인(체크된) 데이터를 리스트 형태로 가져옴, search.html 24라인의 name 참고
    keyword = request.form['keyword'] # search.html에서 form 데이터 중 name이 keyword인 데이터를 가져옴
    select_news = []
    #메일 전송
    smtp = smtplib.SMTP('smtp.naver.com', 587)
    smtp.ehlo()
    smtp.starttls()
    smtp.login('id','pw')

    myemail = 'myemail'
    youremail = request.form['email']
    
    try: # 동작 시도
        # id 추출, 추출한 id로 url 추출
        for s in selected: # for문으로 selected 리스트에 저장된 결과들을 하나씩 확인
            id = int(s) # 정수형으로 id 저장
            url = request.form['url_'+str(id)] # url_로 시작하는 데이터 중에서 id 값이 있는 데이터를 가져옴, search.html 25라인의 name 참고
            title = request.form['title_'+str(id)]
            # 체크박스가 클릭되면 해당 기사의 id를 가져오기 위해 search.html의 24라인 작성
            # 각 기사의 링크 값을 가져오기 위해 search.html의 25라인 작성
            # ['url_'+str(id)]는 search.html에서 hidden input태그를 사용해 시각화되지 않은채로 POST 전송됨
            data = {
                'text': '[' + str(id) + ']번 '+ keyword + ' 관련 기사  제목: '+ title + ' \n 링크 : ' + url # 슬랙에 출력될 메시지
            }
            message_response = requests.post(SLACK_URL, headers=headers, data=json.dumps(data)) # 슬랙 봇에 메시지를 전송, request 모듈을 사용해 POST 요청
            select_news.append(f'제목: {title} / 링크: {url}\n')
        
        print(f"data:{select_news}")
        subject = f'{keyword} 관련 구글 뉴스' 
        message = f'{keyword}(과/와) 관련된 선택한 뉴스 목록입니다. \n'
        for news in select_news:
            message = f'{message + news}\n' 
        msg = MIMEText(message.encode('utf-8'), _subtype='plain', _charset='utf-8')
        msg['Subject'] = Header(subject.encode('utf-8'), 'utf-8')
        msg['From'] = myemail
        msg['To'] = youremail
        smtp.sendmail(myemail,youremail,msg.as_string())
        smtp.quit() 
        return redirect('/') # 초기 화면으로 돌아감
    except SlackApiError as e: # try부분의 코드 동작 실패 시
        return jsonify({'error':e}) # 에러 메시지 json형태로 출력
   
if __name__ == '__main__':
    app.run(port=8080, debug=True) # localhost:8080으로 접속