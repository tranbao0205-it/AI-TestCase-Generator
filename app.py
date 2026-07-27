"""
AI Test Case Generator - Main Flask Application
Hệ thống AI Chatbot tự động sinh test case cho website
"""

import os
import json
import re
import unicodedata
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

from services.ai_service import AIService
from services.excel_service import ExcelService
from services.file_reader import FileReader
from services.history_service import HistoryService
from database.database import init_db
load_dotenv()
app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24).hex())
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'outputs'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 
ALLOWED_EXTENSIONS = {'txt', 'docx', 'pdf', 'md', 'xlsx', 'xlsm', 'xls',
                      'jpg', 'jpeg', 'png', 'gif', 'webp'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)
os.makedirs('instance', exist_ok=True)
init_db()
ai_service = None
excel_service = ExcelService()
file_reader = FileReader()
history_service = HistoryService()
def get_ai_service():
    """Create the AI service lazily so import and tests are not blocked."""
    global ai_service
    if ai_service is None:
        ai_service = AIService()
    return ai_service

def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def clean_project_name_for_file(raw_name: str) -> str:
    """
    Chuẩn hoá tên dự án dùng làm phần đầu filename Excel: bỏ dấu tiếng
    Việt, loại ký tự đặc biệt, giới hạn độ dài. Dùng chung cho cả
    /api/generate-excel và /api/history/<id>/test-cases (Lưu thay đổi)
    để hai luồng tạo file luôn đặt tên nhất quán.
    """
    name = unicodedata.normalize('NFD', str(raw_name or ''))
    name = ''.join(c for c in name if unicodedata.category(c) != 'Mn')
    name = unicodedata.normalize('NFC', name)
    name = re.sub(r'[^\w\s\-]', '', name)
    name = name.strip()[:60]
    return name or 'Project'

def normalize_text(value: str) -> str:
    """Normalize text for comparing labels from Excel rows and test-case features."""
    if not value:
        return ''
    normalized = unicodedata.normalize('NFKD', value)
    normalized = normalized.encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'\s+', ' ', normalized).strip().lower()

def normalize_status(value: str) -> str:
    """Normalize common status values from Excel into canonical status strings."""
    if not value:
        return 'Not Run'
    cleaned = value.strip()
    if not cleaned:
        return 'Not Run'
    lowered = cleaned.lower()
    if lowered in {'passed', 'pass'}:
        return 'Passed'
    if lowered in {'failed', 'fail'}:
        return 'Failed'
    if lowered in {'not run', 'notrun', 'not-ran', 'not ran'}:
        return 'Not Run'
    if lowered in {'blocked', 'block'}:
        return 'Blocked'
    return cleaned

def extract_excel_statuses(content: str) -> dict:
    """Extract a simple label -> status mapping from Excel-like text content."""
    if not content:
        return {}
    statuses = {}
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        match = re.match(r'^(.*?)\s*[|\t]\s*(Passed|Failed|Not Run|NotRun|Blocked|Pass|Fail|Block)\s*$', line, re.IGNORECASE)
        if not match:
            continue
        label = match.group(1).strip()
        status = normalize_status(match.group(2))
        if label:
            statuses[normalize_text(label)] = status
    return statuses

def labels_match(candidate: str, excel_label: str) -> bool:
    """Return True when a testcase label and an Excel label refer to the same feature."""
    candidate_norm = normalize_text(candidate)
    excel_norm = normalize_text(excel_label)
    if not candidate_norm or not excel_norm:
        return False
    if candidate_norm == excel_norm:
        return True
    if candidate_norm in excel_norm or excel_norm in candidate_norm:
        return True
    candidate_tokens = set(candidate_norm.split())
    excel_tokens = set(excel_norm.split())
    if not candidate_tokens or not excel_tokens:
        return False
    overlap = candidate_tokens & excel_tokens
    if not overlap:
        return False
    return len(overlap) / min(len(candidate_tokens), len(excel_tokens)) >= 0.5


def normalize_test_case_data(test_cases_data: dict) -> dict:
    """Ensure uploaded or imported testcase data has the expected structure."""
    if not isinstance(test_cases_data, dict):
        return {}
    modules = test_cases_data.get('modules', {})
    if not isinstance(modules, dict):
        return {}
    normalized_modules = {}
    for module_name, test_cases in modules.items():
        if not isinstance(test_cases, list):
            continue
        normalized_tests = []
        for index, tc in enumerate(test_cases):
            if not isinstance(tc, dict):
                continue

            normalized_tests.append({
                'id': tc.get('id') or f'TC-{index + 1:03d}',
                'module': tc.get('module') or module_name,
                'feature': tc.get('feature') or '',
                'title': tc.get('title') or tc.get('feature') or '',
                'description': tc.get('description') or tc.get('scenario') or '',
                'scenario': tc.get('scenario') or '',
                'given': tc.get('given') or '',
                'when': tc.get('when') or '',
                'then': tc.get('then') or '',
                'precondition': tc.get('precondition') or '',
                'steps': tc.get('steps') or '',
                'test_data': tc.get('test_data') or '',
                'expected_result': tc.get('expected_result') or '',
                'priority': tc.get('priority') or 'Trung bình',
                'test_type': tc.get('test_type') or 'Kiểm thử chức năng',
                'actual_result': tc.get('actual_result') or '',
                'status': tc.get('status') or 'Chưa chạy',
                'note': tc.get('note') or '',
            })

        if normalized_tests:
            normalized_modules[module_name] = normalized_tests
    normalized_data = dict(test_cases_data)
    normalized_data['project_name'] = test_cases_data.get('project_name') or 'Project'
    normalized_data['description'] = test_cases_data.get('description') or 'Imported test cases'
    normalized_data['modules'] = normalized_modules
    return normalized_data


def parse_prewritten_test_cases(content: str) -> dict | None:
    """Parse uploaded content if it already contains structured test case JSON."""
    if not content:
        return None
    text = content.strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except Exception:
        return None
    if isinstance(parsed, dict) and isinstance(parsed.get('modules'), dict):
        return normalize_test_case_data(parsed)
    return None


def apply_excel_statuses(test_cases_data: dict, excel_content: str) -> dict:
    """Overlay Excel-derived statuses onto generated test cases when available."""
    if not excel_content:
        return test_cases_data
    statuses = extract_excel_statuses(excel_content)
    if not statuses:
        return test_cases_data
    modules = test_cases_data.get('modules', {})
    for module_name, test_cases in modules.items():
        for tc in test_cases:
            feature = tc.get('feature', '') or ''
            scenario = tc.get('scenario', '') or ''
            module_value = tc.get('module', module_name) or module_name
            label_candidates = [feature, scenario, tc.get('id', ''), module_value, module_name]
            matched_status = None
            for label in label_candidates:
                for excel_label, status in statuses.items():
                    if labels_match(label, excel_label):
                        matched_status = status
                        break
                if matched_status is not None:
                    break
            if matched_status is not None:
                tc['status'] = matched_status
    return test_cases_data

_OUTCOME_SUFFIXES = (' không thành công', ' thất bại', ' thành công')
def get_base_module_name(module_name: str) -> str:
    """Trả về base_feature (chức năng gốc), bỏ hậu tố nhóm kết quả:
    'thành công' / 'không thành công' / 'thất bại'
    (không phân biệt hoa thường, đã trim khoảng trắng). Dùng để đếm số
    chức năng nghiệp vụ hiển thị, đồng bộ với buildDisplayGroups() ở app.js.

    Lưu ý: hàm này CHỈ dùng để TÍNH total_features. Không dùng để đổi giá
    trị module/feature hiển thị trong bảng test case."""
    if not module_name:
        return module_name
    trimmed = module_name.strip()
    lowered = trimmed.lower()
    for suffix in _OUTCOME_SUFFIXES:
        if lowered.endswith(suffix):
            return trimmed[:-len(suffix)].strip()
    return trimmed
def count_business_modules(modules: dict, requested_functions: list | None = None) -> int:
    """Đếm total_features (số chức năng nghiệp vụ GỐC), không tính theo
    module/group (thành công / không thành công / thất bại).
    Ưu tiên dùng requested_functions (danh sách chức năng người dùng đã yêu
    cầu trong request ban đầu) nếu có — vì đây là nguồn đáng tin cậy nhất.
    Chỉ khi không có mới fallback về suy ra base_feature từ tên module do
    AI sinh ra (không hard-code riêng cho bất kỳ chức năng cụ thể nào).
    """
    if requested_functions:
        base_names = {
            get_base_module_name(str(f)) for f in requested_functions if str(f).strip()
        }
        if base_names:
            return len(base_names)
    if not isinstance(modules, dict):
        return 0
    base_names = set()
    for module_name in modules.keys():
        base_names.add(get_base_module_name(module_name))
    return len(base_names)
def get_previous_test_cases(conversation_id) -> dict | None:
    """Lấy toàn bộ snapshot mới nhất, bao gồm metadata workflow."""
    if not conversation_id:
        return None
    try:
        payload = history_service.get_latest_assistant_payload(int(conversation_id))
        if isinstance(payload, dict) and isinstance(payload.get('modules'), dict):
            return payload
    except Exception as exc:
        app.logger.warning('Không tải được previous_test_cases: %s', exc)
    return None
@app.route('/')
def index():
    """Render main chatbot interface."""
    return render_template('index.html')
@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Receive user message, generate test cases via AI,
    save to history, and return structured result.
    """
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'error': 'Thiếu nội dung message'}), 400
    message = data.get('message', '').strip()
    display_message = (data.get('display_message') or message).strip()
    conversation_id = data.get('conversation_id')
    context_mode = (data.get('context_mode') or 'new').strip().lower()
    if context_mode not in {'new', 'screen_only', 'workflow'}:
        context_mode = 'new'
    uploaded_content = data.get('uploaded_content', '')
    image_blocks = data.get('image_blocks') or None
    image_filenames = data.get('image_filenames') or None
    if not message and not image_blocks:
        return jsonify({'error': 'Message không được để trống'}), 400
    if not message and image_blocks:
        message = 'Phân tích giao diện'
    try:
        result = parse_prewritten_test_cases(uploaded_content)
        if result is None:
            previous_test_cases = None
            if context_mode == 'workflow' and conversation_id:
                previous_test_cases = get_previous_test_cases(conversation_id)
            result = get_ai_service().generate_test_cases(
                message,
                previous_test_cases=previous_test_cases,
                image_blocks=image_blocks,
                context_mode=context_mode,
            )
        result = apply_excel_statuses(result, uploaded_content)
        modules = result.get('modules', {})
        total_tc = sum(len(v) for v in modules.values() if isinstance(v, list))
        requested_functions = result.get('requested_functions')
        module_count = count_business_modules(modules, requested_functions)
        parent_snapshot_id = None
        if context_mode == 'workflow' and conversation_id:
            parent_snapshot_id = history_service.get_latest_assistant_message_id(
                int(conversation_id)
            )
        project_name = result.get('project_name', '').strip()
        conv_title = project_name if project_name and project_name not in ('Project', 'Dự án') else ''
        saved = history_service.save_message(
            conversation_id=conversation_id,
            user_message=display_message,
            ai_response=json.dumps(result, ensure_ascii=False),
            title=conv_title,
            image_filenames=image_filenames,
            context_mode=context_mode,
            parent_snapshot_id=parent_snapshot_id,
            return_details=True,
        )
        conversation_id = saved['conversation_id']
        snapshot_id = saved['snapshot_id']
        project_name = result.get('project_name', '').strip()
        if project_name and project_name not in ('Project', 'Dự án') and conversation_id:
            history_service.update_conversation_title(conversation_id, project_name)

        return jsonify({
            'success': True,
            'conversation_id': conversation_id,
            'snapshot_id': snapshot_id,
            'test_cases': result,
            'summary': {
                'module_count': module_count,
                'total_tc': total_tc,
                'project_name': result.get('project_name', 'Project'),
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
@app.route('/api/upload', methods=['POST'])
def upload_file():
    """
    Accept file upload (.txt, .docx, .pdf, .md, .xlsx, .xlsm, .xls),
    read content and return it for AI processing.
    """
    if 'file' not in request.files:
        return jsonify({'error': 'Không tìm thấy file trong request'}), 400
    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({'error': 'Chưa chọn file'}), 400
    if not allowed_file(file.filename):
        return jsonify({
            'error': 'Định dạng file không hỗ trợ. Chỉ chấp nhận: .txt, .docx, .pdf, .md, .xlsx, .jpg, .jpeg, .png, .webp'
        }), 400
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        if file_reader.is_image(filepath):
            image_block = file_reader.read_image_as_base64(filepath)
            if isinstance(image_block, dict) and image_block.get('type') == 'image_url':
                if isinstance(image_block.get('image_url'), dict):
                    image_block['image_url']['detail'] = 'high'
            return jsonify({
                'success': True,
                'filename': filename,
                'is_image': True,
                'image_block': image_block,
                'preview': f'[Ảnh: {filename}]',
                'full_content': '',
                'char_count': 0,
            })
        content = file_reader.read_file(filepath)
        return jsonify({
            'success': True,
            'filename': filename,
            'is_image': False,
            'preview': content[:300] + '...' if len(content) > 300 else content,
            'full_content': content,
            'char_count': len(content),
        })

    except Exception as e:
        return jsonify({'error': f'Lỗi khi đọc file: {str(e)}'}), 500
@app.route('/api/generate-excel', methods=['POST'])
def generate_excel():
    """
    Receive test case data, create a formatted Excel file,
    save record, and return download URL.
    """
    data = request.get_json()
    if not data or 'test_cases' not in data:
        return jsonify({'error': 'Thiếu dữ liệu test case'}), 400
    try:
        test_cases = data['test_cases']
        raw_name = data.get('project_name', '').strip()
        if not raw_name:
            raw_name = test_cases.get('project_name', 'My Project') or 'My Project'
        project_name = clean_project_name_for_file(raw_name)
        conversation_id = data.get('conversation_id')
        snapshot_id = data.get('snapshot_id')
        filename = excel_service.create_excel(test_cases, project_name)
        if conversation_id:
            history_service.update_excel_file(
                int(conversation_id),
                filename,
                snapshot_id=int(snapshot_id) if snapshot_id else None,
            )
        elif snapshot_id:
            history_service.update_snapshot_excel_file(int(snapshot_id), filename)
        modules = test_cases.get('modules', {})
        total_tc = sum(len(v) for v in modules.values() if isinstance(v, list))
        history_service.save_file_record(
            filename,
            project_name,
            total_tc,
            conversation_id=int(conversation_id) if conversation_id else None,
            snapshot_id=int(snapshot_id) if snapshot_id else None,
        )
        return jsonify({
            'success': True,
            'filename': filename,
            'download_url': f'/download/{filename}',
            'total_tc': total_tc,
        })
    except Exception as e:
        return jsonify({'error': f'Lỗi khi tạo Excel: {str(e)}'}), 500
@app.route('/uploads/<path:filename>')
def serve_uploaded_image(filename: str):
    """
    Phục vụ lại ảnh đã upload (lưu ở uploads/) để hiển thị trong bubble chat
    khi load lại conversation cũ hoặc sau khi reload trang — hỗ trợ tính
    năng tự động lưu ảnh.
    """
    safe_filename = os.path.basename(filename)
    if not safe_filename:
        return jsonify({'error': 'Tên file không hợp lệ'}), 400
    return send_from_directory(app.config['UPLOAD_FOLDER'], safe_filename)
@app.route('/download/<path:filename>')
def download_file(filename: str):
    """Serve Excel file for download."""
    safe_filename = os.path.basename(filename)
    if not safe_filename or safe_filename.startswith('.'):
        return jsonify({'error': 'Tên file không hợp lệ'}), 400
    return send_from_directory(
        app.config['OUTPUT_FOLDER'],
        safe_filename,
        as_attachment=True
    )
@app.route('/api/history', methods=['GET'])
def get_history():
    """Return list of conversations and generated files."""
    try:
        conversations = history_service.get_conversations()
        files = history_service.get_files()
        return jsonify({
            'conversations': conversations,
            'files': files,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
@app.route('/api/history/<int:conversation_id>', methods=['GET'])
def get_conversation(conversation_id: int):
    """Return all messages for a specific conversation."""
    try:
        messages = history_service.get_conversation_messages(conversation_id)
        return jsonify({'messages': messages})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
@app.route('/api/history/<int:conversation_id>/title', methods=['PATCH'])
def update_conversation_title(conversation_id: int):
    """Update conversation title with AI-generated project_name."""
    try:
        data = request.get_json()
        title = (data.get('title') or '').strip()
        if not title:
            return jsonify({'error': 'title is required'}), 400
        history_service.update_conversation_title(conversation_id, title)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
@app.route('/api/history/<int:conversation_id>/test-cases', methods=['PUT'])
def update_conversation_test_cases(conversation_id: int):
    """
    Lưu bộ test case (đã được user chỉnh sửa tay trong preview panel)
    xuống DB, đè lên đúng snapshot assistant của conversation.
    Được gọi khi user bấm "Lưu thay đổi".

    Sau khi lưu DB thành công, TỰ ĐỘNG tạo một file Excel MỚI từ dữ liệu
    testcase vừa lưu (module/scenario/expected_result/priority/... đã
    chỉnh sửa) — KHÔNG ghi đè file Excel cũ, mỗi lần lưu sinh 1 filename
    riêng biệt theo timestamp (do ExcelService.create_excel đảm nhiệm).
    """
    try:
        data = request.get_json()
        test_cases = data.get('test_cases') if data else None
        if not test_cases or not isinstance(test_cases, dict):
            return jsonify({'error': 'test_cases không hợp lệ'}), 400
        snapshot_id = data.get('snapshot_id')
        existing_payload = None
        if snapshot_id:
            existing_payload = history_service.get_snapshot_payload(
                int(snapshot_id), conversation_id=conversation_id
            )
        else:
            existing_payload = history_service.get_latest_assistant_payload(conversation_id)
        if isinstance(existing_payload, dict):
            for key in ('_screen_context', '_workflow_relation', '_workflow_context'):
                if key not in test_cases and key in existing_payload:
                    test_cases[key] = existing_payload[key]
        if snapshot_id:
            target_snapshot_id = int(snapshot_id)
            ok = history_service.update_snapshot_ai_message(
                snapshot_id=target_snapshot_id,
                conversation_id=conversation_id,
                ai_response=json.dumps(test_cases, ensure_ascii=False),
            )
        else:
            ok = history_service.update_last_ai_message(
                conversation_id=conversation_id,
                ai_response=json.dumps(test_cases, ensure_ascii=False),
            )
            target_snapshot_id = history_service.get_latest_assistant_message_id(conversation_id)
        if not ok:
            return jsonify({'error': 'Không tìm thấy conversation hoặc chưa có test case'}), 404
        raw_name = (test_cases.get('project_name') or '').strip() or 'My Project'
        project_name = clean_project_name_for_file(raw_name)
        filename = excel_service.create_excel(test_cases, project_name)

        modules = test_cases.get('modules', {})
        total_testcases = sum(len(v) for v in modules.values() if isinstance(v, list))
        history_service.update_excel_file(
            int(conversation_id), filename, snapshot_id=target_snapshot_id,
        )
        history_service.save_file_record(
            filename,
            project_name,
            total_testcases,
            conversation_id=int(conversation_id),
            snapshot_id=target_snapshot_id,
        )

        return jsonify({
            'success': True,
            'message': 'Đã lưu thay đổi và tạo file Excel mới',
            'filename': filename,
            'download_url': f'/download/{filename}',
            'total_testcases': total_testcases,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
@app.route('/api/history/<int:conversation_id>/test-cases/regenerate', methods=['POST'])
def regenerate_test_cases(conversation_id: int):
    """
    Sinh lại testcase theo phạm vi do người dùng chọn trong popup Chỉnh
    sửa Test Case:
      - scope = "single_testcase": chỉ sinh lại đúng 1 testcase, giữ
        nguyên ID/vị trí/chức năng, các testcase khác không đổi.
      - scope = "entire_function": chỉ sinh lại toàn bộ testcase của
        đúng 1 chức năng, các chức năng khác không đổi.
    Payload single_testcase: {scope, module_name, testcase_id, testcase, snapshot_id?}
    Payload entire_function : {scope, module_name, testcases, snapshot_id?}
    """
    data = request.get_json(silent=True) or {}
    scope = (data.get('scope') or '').strip()
    module_name = (data.get('module_name') or '').strip()
    snapshot_id = data.get('snapshot_id')

    if scope not in ('single_testcase', 'entire_function'):
        return jsonify({'error': 'scope không hợp lệ, chỉ nhận single_testcase hoặc entire_function'}), 400
    if not module_name:
        return jsonify({'error': 'Thiếu module_name'}), 400

    try:
        payload = None
        if snapshot_id:
            payload = history_service.get_snapshot_payload(int(snapshot_id), conversation_id=conversation_id)
        if payload is None:
            payload = history_service.get_latest_assistant_payload(conversation_id)
        if not isinstance(payload, dict) or not isinstance(payload.get('modules'), dict):
            return jsonify({'error': 'Không tìm thấy dữ liệu test case của cuộc trò chuyện này'}), 404

        modules = payload['modules']
        project_name = payload.get('project_name', '') or ''

        if scope == 'single_testcase':
            testcase = data.get('testcase')
            testcase_id = (data.get('testcase_id') or '').strip()
            if not isinstance(testcase, dict) or not testcase_id:
                return jsonify({'error': 'Thiếu testcase hoặc testcase_id'}), 400
            tcs = modules.get(module_name)
            if not isinstance(tcs, list):
                return jsonify({'error': f'Không tìm thấy chức năng "{module_name}"'}), 404
            idx = next(
                (i for i, t in enumerate(tcs) if isinstance(t, dict) and t.get('id') == testcase_id),
                None,
            )
            if idx is None:
                return jsonify({'error': f'Không tìm thấy test case {testcase_id} trong chức năng "{module_name}"'}), 404
            new_tc = get_ai_service().regenerate_single_testcase(module_name, testcase, project_name)
            new_tc['id'] = testcase_id
            tcs[idx] = new_tc
        else:
            testcases = data.get('testcases')
            if not isinstance(testcases, list) or not testcases:
                return jsonify({'error': 'Thiếu danh sách testcases'}), 400
            if module_name not in modules:
                return jsonify({'error': f'Không tìm thấy chức năng "{module_name}"'}), 404
            new_list = get_ai_service().regenerate_entire_function(module_name, testcases, project_name)
            modules[module_name] = new_list
            seq = 1
            for tcs in modules.values():
                if not isinstance(tcs, list):
                    continue
                for tc in tcs:
                    if isinstance(tc, dict):
                        tc['id'] = f"TC_{seq:03d}"
                        seq += 1

        payload['modules'] = modules
        target_snapshot_id = int(snapshot_id) if snapshot_id else history_service.get_latest_assistant_message_id(conversation_id)
        if not target_snapshot_id:
            return jsonify({'error': 'Không xác định được snapshot để lưu'}), 404
        ok = history_service.update_snapshot_ai_message(
            snapshot_id=target_snapshot_id,
            conversation_id=conversation_id,
            ai_response=json.dumps(payload, ensure_ascii=False),
        )
        if not ok:
            return jsonify({'error': 'Lưu lịch sử thất bại'}), 500
        try:
            history_service.update_snapshot_excel_file(target_snapshot_id, '')
        except Exception:
            pass

        return jsonify({
            'success': True,
            'snapshot_id': target_snapshot_id,
            'module_name': module_name,
            'test_cases': payload,
        })
    except RuntimeError as exc:
        return jsonify({'error': str(exc)}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500
@app.route('/api/files/<path:filename>', methods=['DELETE'])
def delete_file(filename: str):
    """Delete a generated Excel file and its database record."""
    try:
        safe_filename = os.path.basename(filename)
        if not safe_filename or safe_filename.startswith('.'):
            return jsonify({'error': 'Tên file không hợp lệ'}), 400
        filepath = os.path.join(app.config['OUTPUT_FOLDER'], safe_filename)
        if os.path.exists(filepath):
            os.remove(filepath)
        history_service.delete_file_record(safe_filename)
        return jsonify({'success': True, 'message': f'Đã xóa file {safe_filename}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
@app.route('/api/status', methods=['GET'])
def api_status():
    """Check if OpenAI API key is configured."""
    api_key = os.environ.get('OPENAI_API_KEY', '')
    has_key = bool(api_key and api_key != 'your-openai-api-key-here')
    return jsonify({
        'status': 'online' if has_key else 'offline',
        'message': 'API Ready' if has_key else 'Chưa cấu hình API key',
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)