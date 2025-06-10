from flask import Blueprint, jsonify, request

from ..db import get_db

bp = Blueprint("quizzes", __name__)


def _require_admin():
    if request.headers.get("X-Admin") != "true":
        return jsonify({"error": "admin only"}), 403
    return None


@bp.route("/admin/quizzes", methods=["POST"])
def create_quiz():
    admin_check = _require_admin()
    if admin_check:
        return admin_check
    data = request.get_json() or {}
    question = data.get("question")
    correct_answer = data.get("correct_answer")
    if not question or not correct_answer:
        return jsonify({"error": "question and correct_answer required"}), 400
    db = get_db()
    cur = db.execute(
        "INSERT INTO quizzes (question, correct_answer) VALUES (?, ?)",
        (question, correct_answer),
    )
    db.commit()
    return jsonify({"id": cur.lastrowid, "question": question}), 201


@bp.route("/admin/quizzes/<int:quiz_id>", methods=["PUT"])
def update_quiz(quiz_id: int):
    admin_check = _require_admin()
    if admin_check:
        return admin_check
    data = request.get_json() or {}
    question = data.get("question")
    correct_answer = data.get("correct_answer")
    db = get_db()
    quiz = db.execute("SELECT id FROM quizzes WHERE id = ?", (quiz_id,)).fetchone()
    if quiz is None:
        return jsonify({"error": "quiz not found"}), 404
    if question:
        db.execute("UPDATE quizzes SET question = ? WHERE id = ?", (question, quiz_id))
    if correct_answer:
        db.execute(
            "UPDATE quizzes SET correct_answer = ? WHERE id = ?",
            (correct_answer, quiz_id),
        )
    db.commit()
    quiz = db.execute(
        "SELECT id, question, correct_answer FROM quizzes WHERE id = ?",
        (quiz_id,),
    ).fetchone()
    return jsonify(
        {
            "id": quiz["id"],
            "question": quiz["question"],
            "correct_answer": quiz["correct_answer"],
        }
    )


@bp.route("/admin/quizzes/<int:quiz_id>", methods=["DELETE"])
def delete_quiz(quiz_id: int):
    admin_check = _require_admin()
    if admin_check:
        return admin_check
    db = get_db()
    quiz = db.execute("SELECT id FROM quizzes WHERE id = ?", (quiz_id,)).fetchone()
    if quiz is None:
        return jsonify({"error": "quiz not found"}), 404
    db.execute("DELETE FROM quizzes WHERE id = ?", (quiz_id,))
    db.commit()
    return "", 204


@bp.route("/quizzes", methods=["GET"])
def list_quizzes():
    db = get_db()
    quizzes = db.execute("SELECT id, question FROM quizzes").fetchall()
    return jsonify([{"id": q["id"], "question": q["question"]} for q in quizzes])


@bp.route("/quizzes/<int:quiz_id>/attempt", methods=["POST"])
def attempt_quiz(quiz_id: int):
    data = request.get_json() or {}
    user_id = data.get("user_id")
    answer = data.get("answer")
    if user_id is None or answer is None:
        return jsonify({"error": "user_id and answer required"}), 400
    db = get_db()
    quiz = db.execute(
        "SELECT correct_answer FROM quizzes WHERE id = ?", (quiz_id,)
    ).fetchone()
    if quiz is None:
        return jsonify({"error": "quiz not found"}), 404
    is_correct = answer == quiz["correct_answer"]
    db.execute(
        "INSERT INTO user_quiz_attempts (user_id, quiz_id, is_correct) VALUES (?, ?, ?)",
        (user_id, quiz_id, is_correct),
    )
    db.commit()
    return jsonify({"is_correct": is_correct})
