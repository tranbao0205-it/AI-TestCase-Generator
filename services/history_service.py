"""
History Service - Manages conversation history and file records in SQLite.
"""
from datetime import datetime
import json
from database.database import get_db
class HistoryService:

    def _ensure_images_table(self, conn):
        conn.execute('''
            CREATE TABLE IF NOT EXISTS message_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        ''')

    def save_message(
        self,
        conversation_id,
        user_message: str,
        ai_response: str,
        title: str = '',
        image_filenames: list | None = None,
        context_mode: str = 'new',
        parent_snapshot_id: int | None = None,
        return_details: bool = False,
    ):
        '''
        Lưu một lượt user/assistant.

        Mỗi message assistant là một snapshot testcase độc lập. Workflow tạo
        snapshot mới và không ghi đè snapshot cũ.
        '''
        conn = get_db()
        try:
            self._ensure_images_table(conn)
            context_mode = (context_mode or 'new').strip().lower()
            if context_mode not in {'new', 'screen_only', 'workflow'}:
                context_mode = 'new'

            if not conversation_id:
                conv_title = title or ((user_message[:60] + '…') if len(user_message) > 60 else user_message)
                cursor = conn.execute(
                    'INSERT INTO conversations (title) VALUES (?)',
                    (conv_title or 'Cuộc trò chuyện',),
                )
                conversation_id = cursor.lastrowid
            elif title:
                conn.execute(
                    'UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?',
                    (title, datetime.now().isoformat(), int(conversation_id)),
                )
            else:
                conn.execute(
                    'UPDATE conversations SET updated_at = ? WHERE id = ?',
                    (datetime.now().isoformat(), int(conversation_id)),
                )

            cursor = conn.execute(
                '''INSERT INTO messages
                   (conversation_id, role, content, context_mode, parent_snapshot_id)
                   VALUES (?, 'user', ?, ?, ?)''',
                (
                    int(conversation_id),
                    user_message,
                    context_mode,
                    int(parent_snapshot_id) if parent_snapshot_id else None,
                ),
            )
            user_message_id = cursor.lastrowid

            if image_filenames:
                for fname in image_filenames:
                    fname = (fname or '').strip()
                    if fname:
                        conn.execute(
                            'INSERT INTO message_images (message_id, filename) VALUES (?, ?)',
                            (user_message_id, fname),
                        )

            cursor = conn.execute(
                '''INSERT INTO messages
                   (conversation_id, role, content, context_mode, parent_snapshot_id)
                   VALUES (?, 'assistant', ?, ?, ?)''',
                (
                    int(conversation_id),
                    ai_response,
                    context_mode,
                    int(parent_snapshot_id) if parent_snapshot_id else None,
                ),
            )
            assistant_message_id = cursor.lastrowid
            conn.commit()

            if return_details:
                return {
                    'conversation_id': int(conversation_id),
                    'user_message_id': int(user_message_id),
                    'assistant_message_id': int(assistant_message_id),
                    'snapshot_id': int(assistant_message_id),
                }
            return int(conversation_id)
        finally:
            conn.close()

    @staticmethod
    def _parse_assistant_payload(content: str | None) -> dict | None:
        """Parse a saved assistant JSON snapshot without dropping workflow metadata."""
        if not content:
            return None
        try:
            payload = json.loads(content)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def get_latest_assistant_payload(self, conversation_id: int) -> dict | None:
        """Return the latest complete assistant snapshot, including _workflow_context."""
        conn = get_db()
        try:
            row = conn.execute(
                """SELECT content FROM messages
                   WHERE conversation_id = ? AND role = 'assistant'
                   ORDER BY id DESC LIMIT 1""",
                (int(conversation_id),),
            ).fetchone()
            return self._parse_assistant_payload(row['content']) if row else None
        finally:
            conn.close()

    def get_snapshot_payload(self, snapshot_id: int, conversation_id: int | None = None) -> dict | None:
        """Return one complete assistant snapshot for safe metadata-preserving edits."""
        conn = get_db()
        try:
            if conversation_id is None:
                row = conn.execute(
                    "SELECT content FROM messages WHERE id = ? AND role = 'assistant'",
                    (int(snapshot_id),),
                ).fetchone()
            else:
                row = conn.execute(
                    """SELECT content FROM messages
                       WHERE id = ? AND conversation_id = ? AND role = 'assistant'""",
                    (int(snapshot_id), int(conversation_id)),
                ).fetchone()
            return self._parse_assistant_payload(row['content']) if row else None
        finally:
            conn.close()

    def get_latest_assistant_message_id(self, conversation_id: int) -> int | None:
        '''Trả snapshot testcase mới nhất của conversation.'''
        conn = get_db()
        try:
            row = conn.execute(
                '''SELECT id FROM messages
                   WHERE conversation_id = ? AND role = 'assistant'
                   ORDER BY id DESC LIMIT 1''',
                (int(conversation_id),),
            ).fetchone()
            return int(row['id']) if row else None
        finally:
            conn.close()

    def update_excel_file(
        self,
        conversation_id: int,
        filename: str,
        snapshot_id: int | None = None,
    ):
        '''Gắn Excel vào conversation và đúng snapshot; không đổi title sidebar.'''
        conn = get_db()
        try:
            conn.execute(
                'UPDATE conversations SET excel_file = ?, updated_at = ? WHERE id = ?',
                (filename, datetime.now().isoformat(), int(conversation_id)),
            )
            if snapshot_id:
                conn.execute(
                    '''UPDATE messages SET excel_file = ?
                       WHERE id = ? AND conversation_id = ? AND role = 'assistant' ''',
                    (filename, int(snapshot_id), int(conversation_id)),
                )
            conn.commit()
        finally:
            conn.close()

    def update_snapshot_excel_file(self, snapshot_id: int, filename: str) -> bool:
        '''Gắn file Excel vào đúng assistant snapshot.'''
        conn = get_db()
        try:
            cursor = conn.execute(
                "UPDATE messages SET excel_file = ? WHERE id = ? AND role = 'assistant'",
                (filename, int(snapshot_id)),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_conversations(self) -> list:
        """Return latest 30 conversations ordered by last update."""
        conn = get_db()
        try:
            rows = conn.execute(
                '''SELECT id, title, excel_file, created_at
                   FROM conversations
                   ORDER BY id DESC
                   LIMIT 30'''
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_snapshot_ai_message(
        self,
        snapshot_id: int,
        conversation_id: int,
        ai_response: str,
    ) -> bool:
        '''Chỉ cập nhật đúng snapshot đang mở trong Preview.'''
        conn = get_db()
        try:
            cursor = conn.execute(
                '''UPDATE messages SET content = ?
                   WHERE id = ? AND conversation_id = ? AND role = 'assistant' ''',
                (ai_response, int(snapshot_id), int(conversation_id)),
            )
            if cursor.rowcount <= 0:
                return False
            conn.execute(
                'UPDATE conversations SET updated_at = ? WHERE id = ?',
                (datetime.now().isoformat(), int(conversation_id)),
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def update_last_ai_message(self, conversation_id: int, ai_response: str) -> bool:
        '''Tương thích frontend cũ: cập nhật snapshot mới nhất.'''
        snapshot_id = self.get_latest_assistant_message_id(conversation_id)
        if not snapshot_id:
            return False
        return self.update_snapshot_ai_message(snapshot_id, conversation_id, ai_response)

    def get_conversation_messages(self, conversation_id: int) -> list:
        """
        Return all messages for a conversation in chronological order.
        Mỗi message user (nếu có ảnh) sẽ kèm thêm field 'images': [filename,...]
        để frontend tự khôi phục lại ảnh đã gửi khi load lại conversation.
        """
    
        conn = get_db()
        try:
            self._ensure_images_table(conn)
            rows = conn.execute(
                '''SELECT id, role, content, context_mode, parent_snapshot_id,
                          excel_file, created_at
                   FROM messages
                   WHERE conversation_id = ?
                   ORDER BY id ASC''',
                (int(conversation_id),),
            ).fetchall()
            messages = [dict(r) for r in rows]

            message_ids = [m['id'] for m in messages]
            if message_ids:
                placeholders = ','.join('?' * len(message_ids))
                img_rows = conn.execute(
                    f'''SELECT message_id, filename FROM message_images
                        WHERE message_id IN ({placeholders})
                        ORDER BY id ASC''',
                    message_ids,
                ).fetchall()
                images_by_msg = {}
                for r in img_rows:
                    images_by_msg.setdefault(r['message_id'], []).append(r['filename'])
                for m in messages:
                    imgs = images_by_msg.get(m['id'])
                    if imgs:
                        m['images'] = imgs

            return messages
        finally:
            conn.close()

    def save_file_record(
        self,
        filename: str,
        project_name: str,
        test_case_count: int,
        conversation_id: int | None = None,
        snapshot_id: int | None = None,
    ):
        '''Lưu file Excel và liên kết với đúng snapshot testcase.'''
        conn = get_db()
        try:
            conn.execute(
                '''INSERT OR REPLACE INTO file_records
                   (filename, project_name, test_case_count, conversation_id, snapshot_id)
                   VALUES (?, ?, ?, ?, ?)''',
                (
                    filename,
                    project_name,
                    int(test_case_count or 0),
                    int(conversation_id) if conversation_id else None,
                    int(snapshot_id) if snapshot_id else None,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_files(self) -> list:
        """Return all file records ordered by creation date (newest first)."""
        conn = get_db()
        try:
            rows = conn.execute(
                '''SELECT filename, project_name, test_case_count,
                          conversation_id, snapshot_id, created_at
                   FROM file_records
                   ORDER BY created_at DESC'''
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def delete_file_record(self, filename: str):
        """Remove a file record by filename."""
        conn = get_db()
        try:
            conn.execute(
                'DELETE FROM file_records WHERE filename = ?', (filename,)
            )
            conn.commit()
        finally:
            conn.close()

    def update_conversation_title(self, conversation_id: int, title: str):
        """Cập nhật title của conversation theo project_name từ AI."""
        conn = get_db()
        try:
            conn.execute(
                'UPDATE conversations SET title = ? WHERE id = ?',
                (title, int(conversation_id)),
            )
            conn.commit()
        finally:
            conn.close()