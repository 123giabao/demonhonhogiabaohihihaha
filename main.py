from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import gspread
from google.oauth2.service_account import Credentials
import uuid
import time
import re
import json
from openai import OpenAI
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'secret123')

# 🔑 DeepSeek API Configuration
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', 'sk-474836e4c7b6462d8a9a24ed964b0251')
deepseek_client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

# 🔑 Kết nối Google Sheets
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

try:

    creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
    
    if creds_json:
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file(
            "credentials.json",
            scopes=SCOPES
        )
    
    client = gspread.authorize(creds)
    print("✅ Kết nối Google Sheets thành công!")
except Exception as e:
    print(f"❌ Lỗi kết nối Google Sheets: {str(e)}")
    client = None

# 📄 Mở sheets
try:
    sheet_users = client.open_by_key("1MN8N3lV1Z_ijA8y8aHseHjFxBntPngOnZQ9vQ9EcGsk").sheet1
    sheet_problems = client.open_by_key("1fiqngxE_wiskJ19WJz1R43Hvu8UqaqWCp3wgMoe5rP4").sheet1
except Exception as e:
    print(f"❌ Lỗi mở sheets: {str(e)}")
    sheet_users = None
    sheet_problems = None

# Sheet submissions
try:
    sheet_submissions = client.open_by_key("10DpZvCkKwNuKGkgHxDGbLrA1apRlaIGpOEhaxWmi-LA").worksheet("Submissions")
except:
    try:
        spreadsheet = client.open_by_key("10DpZvCkKwNuKGkgHxDGbLrA1apRlaIGpOEhaxWmi-LA")
        sheet_submissions = spreadsheet.add_worksheet(title="Submissions", rows="1000", cols="10")
        sheet_submissions.append_row([
            "Username", "Problem", "Language", "Code", "Score", "Result", 
            "Feedback", "Timestamp", "Strengths", "Weaknesses"
        ])
    except:
        sheet_submissions = None

# 🆕 Sheet lịch sử học tập
try:
    spreadsheet = client.open_by_key("10DpZvCkKwNuKGkgHxDGbLrA1apRlaIGpOEhaxWmi-LA")
    sheet_lichsu = spreadsheet.worksheet("LichSuHocTap")
    print("✅ Đã kết nối Sheet LichSuHocTap")
except:
    try:
        spreadsheet = client.open_by_key("10DpZvCkKwNuKGkgHxDGbLrA1apRlaIGpOEhaxWmi-LA")
        sheet_lichsu = spreadsheet.add_worksheet(title="LichSuHocTap", rows="1000", cols="20")
        sheet_lichsu.append_row([
            "Username", "TotalSubmissions", "AverageScore", "LastUpdated",
            "RecentCodes", "RecentProblems", "RecentScores", "RecentFeedbacks",
            "OverallStrengths", "OverallWeaknesses", "LearningTrend",
            "ThinkingStyle", "FocusAreas", "LastAnalysis"
        ])
        print("✅ Đã tạo Sheet LichSuHocTap mới")
    except Exception as e:
        print(f"❌ Lỗi tạo Sheet LichSuHocTap: {str(e)}")
        sheet_lichsu = None

# Lưu trữ tạm kết quả submission
submission_results = {}

# 🎨 Danh sách GIF ngẫu nhiên
RANDOM_GIFS = [
    "https://i.giphy.com/media/v1.Y2lkPTc5MGI3NjExcHE3ZnNveGhyYTdvdDFxMnBoZTM4eWg5aDQ3OWJ6N2J5c3Y3ejJpZyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/26tn33aiTi1jkl6H6/giphy.gif",
    "https://i.giphy.com/media/v1.Y2lkPTc5MGI3NjExZjBhMmRicnRzNHBvdGw2eHdwZXByeXVob3BqbDk5dXNqc2I0cG1mayZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/Dh5q0sShxgp13DwrvG/giphy.gif",
    "https://i.giphy.com/media/v1.Y2lkPTc5MGI3NjExOXlhOGdxNGV0cWF1OHo1dXdtenB3aGNqNmFyYWo1eGVneGhucjlxdCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/L8K62iTDkzGX6/giphy.gif",
    "https://i.giphy.com/media/v1.Y2lkPTc5MGI3NjExNjJ3aGFsd2dnN3RnYmRoMWF6ZnNkMHl6eXh3Y2FvMGVoYzd1dTl1ayZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/JIX9t2j0ZTN9S/giphy.gif",
    "https://i.giphy.com/media/v1.Y2lkPTc5MGI3NjExMnFjN3NncXJydzh3ZDd2OHltYmdvenRmZGhjMW9yNGMxZGNsMmJhcSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/3oKIPnAiaMCws8nOsE/giphy.gif"
]


def get_correct_answer(problem_title):
    """Lấy đáp án đúng từ Google Sheets"""
    try:
        data = sheet_problems.get_all_values()
        for row in data[1:]:
            if row[0] == problem_title:
                return row[2] if len(row) > 2 else ""
        return None
    except Exception as e:
        print(f"❌ Lỗi lấy đáp án: {str(e)}")
        return None


def save_to_lichsu(username, submission_data):
    """Lưu lịch sử vào Sheet LichSuHocTap"""
    if sheet_lichsu is None:
        print("❌ Sheet LichSuHocTap không khả dụng")
        return False
    
    try:
        all_data = sheet_lichsu.get_all_values()
        user_row_idx = None
        
        for idx, row in enumerate(all_data[1:], start=2):
            if len(row) > 0 and row[0] == username:
                user_row_idx = idx
                break
        
        recent_submissions = []
        submissions_data = sheet_submissions.get_all_values()
        for row in submissions_data[1:]:
            if len(row) > 0 and row[0] == username:
                recent_submissions.append({
                    'problem': row[1] if len(row) > 1 else '',
                    'code': row[3][:200] if len(row) > 3 else '',
                    'score': row[4] if len(row) > 4 else '0',
                    'feedback': row[6][:100] if len(row) > 6 else ''
                })
        
        if not recent_submissions:
            print(f"⚠️ {username} chưa có submission nào")
            return False
        
        recent_submissions = recent_submissions[-10:]
        
        try:
            scores = [float(s['score']) for s in recent_submissions if s['score']]
            avg_score = sum(scores) / len(scores) if scores else 0
        except:
            avg_score = 0
        
        recent_codes = " ||| ".join([s['code'] for s in recent_submissions])
        recent_problems = " ||| ".join([s['problem'] for s in recent_submissions])
        recent_scores = ", ".join([str(s['score']) for s in recent_submissions])
        recent_feedbacks = " ||| ".join([s['feedback'] for s in recent_submissions])
        
        new_data = [
            username,
            str(len(recent_submissions)),
            str(round(avg_score, 2)),
            time.strftime('%Y-%m-%d %H:%M:%S'),
            recent_codes,
            recent_problems,
            recent_scores,
            recent_feedbacks,
            "", "", "", "", "", ""
        ]
        
        if user_row_idx:
            sheet_lichsu.update(f'A{user_row_idx}:N{user_row_idx}', [new_data])
            print(f"✅ Đã cập nhật lịch sử cho {username}")
        else:
            sheet_lichsu.append_row(new_data)
            print(f"✅ Đã thêm lịch sử mới cho {username}")
        
        return True
    except Exception as e:
        print(f"❌ Lỗi lưu lịch sử: {str(e)}")
        return False


def update_analysis_to_lichsu(username, analysis_result):
    """Cập nhật kết quả phân tích vào Sheet LichSuHocTap"""
    try:
        all_data = sheet_lichsu.get_all_values()
        user_row_idx = None
        
        for idx, row in enumerate(all_data[1:], start=2):
            if row[0] == username:
                user_row_idx = idx
                break
        
        if not user_row_idx:
            return False
        
        sheet_lichsu.update(f'I{user_row_idx}', [[", ".join(analysis_result.get('strengths', []))]])
        sheet_lichsu.update(f'J{user_row_idx}', [[", ".join(analysis_result.get('weaknesses', []))]])
        sheet_lichsu.update(f'K{user_row_idx}', [[analysis_result.get('learning_trend', '')]])
        sheet_lichsu.update(f'L{user_row_idx}', [[analysis_result.get('thinking_style', '')]])
        sheet_lichsu.update(f'M{user_row_idx}', [[", ".join(analysis_result.get('focus_areas', []))]])
        sheet_lichsu.update(f'N{user_row_idx}', [[time.strftime('%Y-%m-%d %H:%M:%S')]])
        
        print(f"✅ Đã cập nhật phân tích cho {username}")
        return True
    except Exception as e:
        print(f"❌ Lỗi cập nhật phân tích: {str(e)}")
        return False


def grade_code_with_deepseek(student_code, correct_answer, problem_title, language):
    """Sử dụng DeepSeek để chấm code"""
    try:
        prompt = f"""Bạn là giáo viên lập trình chuyên nghiệp. Hãy chấm bài của học sinh.

**Đề bài:** {problem_title}

**Đáp án chuẩn:**
```{language}
{correct_answer}
```

**Code học sinh:**
```{language}
{student_code}
```

Hãy phân tích và trả về JSON với định dạng:
{{
    "score": <điểm từ 0-100>,
    "result": "<PASS/FAIL>",
    "feedback": "<nhận xét tổng quan>",
    "strengths": ["điểm mạnh 1", "điểm mạnh 2"],
    "weaknesses": ["điểm yếu 1", "điểm yếu 2"],
    "suggestions": ["gợi ý cải thiện 1", "gợi ý 2"]
}}

Chấm điểm dựa trên:
- Logic đúng (40%)
- Độ tối ưu (30%)
- Clean code (20%)
- Xử lý edge cases (10%)"""

        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "Bạn là giáo viên lập trình chuyên nghiệp, trả về JSON hợp lệ."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        
        result_text = response.choices[0].message.content.strip()
        
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()
        
        result = json.loads(result_text)
        return result
        
    except json.JSONDecodeError as e:
        print(f"❌ Lỗi parse JSON: {str(e)}")
        return {
            "score": 50,
            "result": "ERROR",
            "feedback": "Không thể phân tích kết quả từ AI",
            "strengths": ["Code đã được gửi thành công"],
            "weaknesses": ["Hệ thống chưa phân tích được"],
            "suggestions": ["Vui lòng thử lại"]
        }
    except Exception as e:
        print(f"❌ Lỗi DeepSeek API: {str(e)}")
        return {
            "score": 0,
            "result": "ERROR",
            "feedback": f"Lỗi kết nối AI: {str(e)}",
            "strengths": [],
            "weaknesses": ["Không thể chấm bài"],
            "suggestions": ["Kiểm tra API key hoặc kết nối mạng"]
        }


def analyze_student_history_with_deepseek(username):
    """Phân tích toàn bộ lịch sử học tập của học sinh bằng DeepSeek"""
    try:
        all_data = sheet_lichsu.get_all_values()
        user_data = None
        
        for row in all_data[1:]:
            if row[0] == username:
                user_data = row
                break
        
        if not user_data or not user_data[4]:
            return {
                "error": "Học sinh chưa có bài làm nào",
                "total_submissions": 0
            }
        
        recent_problems = user_data[5].split(" ||| ") if len(user_data) > 5 else []
        recent_scores = user_data[6].split(", ") if len(user_data) > 6 else []
        recent_feedbacks = user_data[7].split(" ||| ") if len(user_data) > 7 else []
        
        submission_summary = "\n\n".join([
            f"""Bài {i+1}: {recent_problems[i] if i < len(recent_problems) else 'N/A'}
Điểm: {recent_scores[i] if i < len(recent_scores) else 'N/A'}
Feedback: {recent_feedbacks[i] if i < len(recent_feedbacks) else 'N/A'}"""
            for i in range(min(len(recent_problems), 10))
        ])
        
        prompt = f"""Bạn là chuyên gia phân tích giáo dục. Hãy phân tích toàn diện học sinh **{username}**.

**Lịch sử làm bài (tổng {user_data[1]} bài):**
**Điểm trung bình: {user_data[2]}**

{submission_summary}

Hãy trả về JSON với định dạng:
{{
    "overall_score": <điểm trung bình 0-100>,
    "learning_trend": "<IMPROVING/STABLE/DECLINING>",
    "strengths": ["điểm mạnh 1", "điểm mạnh 2", "điểm mạnh 3"],
    "weaknesses": ["điểm yếu 1", "điểm yếu 2"],
    "thinking_style": "<mô tả lối tư duy>",
    "recommendations": ["khuyến nghị 1", "khuyến nghị 2", "khuyến nghị 3"],
    "focus_areas": ["chủ đề cần tập trung 1", "chủ đề 2"],
    "summary": "<tóm tắt tổng quan 2-3 câu>"
}}

Phân tích sâu:
- Xu hướng tiến bộ theo thời gian
- Phong cách code (clean code, tối ưu, xử lý lỗi...)
- Khả năng logic và thuật toán
- Điểm cần cải thiện ưu tiên
- Luôn nói xin chào"""

        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "Bạn là chuyên gia phân tích giáo dục, trả về JSON hợp lệ."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=2500
        )
        
        result_text = response.choices[0].message.content.strip()
        
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()
        
        result = json.loads(result_text)
        result['total_submissions'] = int(user_data[1]) if user_data[1] else 0
        result['recent_scores'] = recent_scores[:5]
        
        update_analysis_to_lichsu(username, result)
        
        return result
        
    except json.JSONDecodeError as e:
        print(f"❌ Lỗi parse JSON: {str(e)}")
        return {"error": "Không thể phân tích dữ liệu"}
    except Exception as e:
        print(f"❌ Lỗi phân tích: {str(e)}")
        return {"error": str(e)}


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        data = sheet_users.get_all_values()

        for row in data[1:]:
            if row[0] == username and row[1] == password:
                session['user'] = username
                return redirect(url_for('index'))

        return render_template('login.html', error="Sai tên hoặc mật khẩu!")

    return render_template('login.html')


@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    import random
    random_gif = random.choice(RANDOM_GIFS)
    
    return render_template('index.html', user=session['user'], random_gif=random_gif)


@app.route('/search', methods=['POST'])
def search():
    if 'user' not in session:
        return jsonify({'error': 'Chưa đăng nhập'}), 403

    query = request.form['query'].lower()
    data = sheet_problems.get_all_values()
    results = []

    for row in data[1:]:
        if query in row[0].lower():
            results.append({'title': row[0], 'content': row[1]})
    return jsonify(results)


@app.route('/get_problem', methods=['POST'])
def get_problem():
    if 'user' not in session:
        return jsonify({'error': 'Chưa đăng nhập'}), 403

    title = request.form['title']
    data = sheet_problems.get_all_values()
    for row in data[1:]:
        if row[0] == title:
            return jsonify({
                'title': row[0],
                'content': row[1],
                'hint1': row[3] if len(row) > 3 else "",
                'hint2': row[4] if len(row) > 4 else "",
                'hint3': row[5] if len(row) > 5 else ""
            })
    return jsonify({'error': 'Không tìm thấy đề'}), 404


@app.route('/submit_code', methods=['POST'])
def submit_code():
    """Chấm code trực tiếp bằng DeepSeek"""
    if 'user' not in session:
        return jsonify({'error': 'Chưa đăng nhập'}), 403

    title = request.form['title']
    code = request.form['code']
    language = request.form['language']
    username = session['user']

    submission_id = str(uuid.uuid4())
    
    submission_results[submission_id] = {
        'status': 'processing',
        'username': username,
        'problem': title,
        'code': code,
        'language': language,
        'timestamp': time.time()
    }

    try:
        correct_answer = get_correct_answer(title)
        
        if not correct_answer:
            return jsonify({
                'success': False,
                'message': '❌ Không tìm thấy đáp án cho bài này'
            })
        
        result = grade_code_with_deepseek(code, correct_answer, title, language)
        
        submission_results[submission_id] = {
            'status': 'completed',
            'result': result['result'],
            'score': result['score'],
            'feedback': result['feedback'],
            'strengths': result.get('strengths', []),
            'weaknesses': result.get('weaknesses', []),
            'suggestions': result.get('suggestions', []),
            'timestamp': time.time()
        }
        
        try:
            sheet_submissions.append_row([
                username,
                title,
                language,
                code[:500],
                result['score'],
                result['result'],
                result['feedback'],
                time.strftime('%Y-%m-%d %H:%M:%S'),
                str(result.get('strengths', [])),
                str(result.get('weaknesses', []))
            ])
            print(f"✅ Đã lưu submission {submission_id} vào Google Sheets")
            
            save_to_lichsu(username, {
                'problem': title,
                'code': code,
                'score': result['score'],
                'feedback': result['feedback']
            })
            
        except Exception as e:
            print(f"⚠️ Không thể lưu vào Sheets: {str(e)}")
        
        return jsonify({
            'success': True,
            'submission_id': submission_id,
            'message': '🎉 Code đã được chấm xong!',
            'immediate_result': submission_results[submission_id]
        })
        
    except Exception as e:
        submission_results[submission_id] = {
            'status': 'error',
            'error': str(e)
        }
        return jsonify({
            'success': False,
            'message': f"❌ Lỗi: {str(e)}"
        })


@app.route('/get_result/<submission_id>', methods=['GET'])
def get_result(submission_id):
    """Frontend lấy kết quả"""
    if 'user' not in session:
        return jsonify({'error': 'Chưa đăng nhập'}), 403
    
    result = submission_results.get(submission_id)
    
    if not result:
        return jsonify({'error': 'Không tìm thấy submission'}), 404
    
    return jsonify(result)


@app.route('/visualize_code', methods=['POST'])
def visualize_code():
    if 'user' not in session:
        return jsonify({'error': 'Chưa đăng nhập'}), 403
    
    try:
        code = request.form.get('code', '')
        language = request.form.get('language', 'python').lower()
        
        if not code.strip():
            return jsonify({'success': False, 'error': 'Code không được để trống'})
        
        mermaid_code = generate_improved_mermaid(code, language)
        
        return jsonify({'success': True, 'mermaid': mermaid_code})
    
    except Exception as e:
        return jsonify({'success': False, 'error': f"Lỗi tạo sơ đồ: {str(e)}"})


def generate_improved_mermaid(code, language):
    """Tạo flowchart từ code"""
    lines = code.split('\n')
    
    mermaid = "flowchart TD\n"
    mermaid += "    Start([Bắt đầu])\n"
    
    node_id = 1
    prev_node = "Start"
    
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or stripped.startswith('//'):
            continue
        
        current_node = f"N{node_id}"
        display_text = stripped[:50].replace('"', "'").replace('(', '[').replace(')', ']')
        
        is_condition = re.match(r'^\s*(if|elif|else if)\s*', stripped, re.IGNORECASE)
        is_loop = re.match(r'^\s*(for|while)\s*', stripped, re.IGNORECASE)
        
        try:
            if is_condition:
                mermaid += f"    {prev_node} --> {current_node}{{\"{display_text}\"}}\n"
            elif is_loop:
                mermaid += f"    {prev_node} --> {current_node}[\"{display_text}\"]\n"
            else:
                mermaid += f"    {prev_node} --> {current_node}[\"{display_text}\"]\n"
            
            prev_node = current_node
            node_id += 1
            
            if node_id > 30:
                mermaid += f"    {prev_node} --> TooLong[\"...Còn nhiều code...\"]\n"
                prev_node = "TooLong"
                break
                
        except:
            continue
    
    mermaid += f"    {prev_node} --> End([Kết thúc])\n"
    return mermaid


@app.route('/analytics/get_students', methods=['GET'])
def get_students():
    """Lấy danh sách học sinh từ Users sheet"""
    if 'user' not in session:
        return jsonify({'error': 'Chưa đăng nhập'}), 403
    
    try:
        data = sheet_users.get_all_values()
        students = []
        
        for row in data[1:]:
            if row[0]:
                students.append({
                    'username': row[0],
                    'name': row[2] if len(row) > 2 and row[2] else row[0]
                })
        
        return jsonify({'success': True, 'students': students})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/analytics/analyze_student', methods=['POST'])
def analyze_student():
    """Phân tích học sinh bằng DeepSeek"""
    if 'user' not in session:
        return jsonify({'error': 'Chưa đăng nhập'}), 403
    
    try:
        username = request.form.get('username')
        
        result = analyze_student_history_with_deepseek(username)
        
        if 'error' in result:
            return jsonify({
                'success': False,
                'error': result['error']
            })
        
        return jsonify({
            'success': True,
            'data': result
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))


app = app