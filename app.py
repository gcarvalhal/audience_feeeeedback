from flask import Flask, render_template, url_for, session
from flask_socketio import SocketIO, emit
from flask_session import Session
import qrcode
import io
import base64
import time


app = Flask(__name__)
app.config["SESSION_TYPE"] = "filesystem"

Session(app)
socketio = SocketIO(app)

feedback_list = []

live_poll = {"question": "Qual tema queres rever?", "options": ["Funções", "Listas", "Dicionários"], "votes": [0, 0, 0]}

quiz_data = [
    {"question": "Qual é o maior planeta do sistema solar?", "options": ["Júpiter", "Saturno", "Marte", "Terra"], "answer": [0], "explanation": "Júpiter é o maior planeta do sistema solar, com um diâmetro de aproximadamente 142.984 km."},
    {"question": "Quem escreveu 'Os Lusíadas'?", "options": ["Luís de Camões", "Eça de Queirós", "José Saramago", "Fernando Pessoa"], "answer": [0], "explanation": "Luís de Camões escreveu 'Os Lusíadas', publicado em 1572."},
    # Podes adicionar mais perguntas aqui...
]

quiz_stats = {"corretas": 0, "erradas": 0}


@app.route("/")
def index():
    feedback_url = url_for("feedback", _external=True)
    poll_url = url_for("poll", _external=True)

    qr = qrcode.make(feedback_url)
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    poll_results = list(zip(live_poll["options"], live_poll["votes"]))

    return render_template("index.html", qr_b64=qr_b64, feedback_list=feedback_list, poll_results=poll_results, poll_url=poll_url)


@app.route("/feedback")
def feedback():
    return render_template("feedback.html")


@app.route("/poll")
def poll():
    poll_options = [{"index": i, "text": opt} for i, opt in enumerate(live_poll["options"])]
    poll_results = list(zip(live_poll["options"], live_poll["votes"]))
    return render_template("poll.html", poll_results=poll_results, poll_options=poll_options, live_poll=live_poll)


@app.route("/quiz")
def quiz():
    return render_template("quiz.html", quiz=quiz_data)


@socketio.on("send_feedback")
def handle_feedback(msg):
    now = time.time()
    last_sent = session.get("last_feedback_time", 0)

    if now - last_sent < 10:
        emit("new_feedback", "⏳ Feedback ignorado: aguarde antes de enviar novamente.")
        return

    session["last_feedback_time"] = now
    feedback_list.append(msg)
    emit("new_feedback", msg, broadcast=True)


@socketio.on("vote")
def handle_vote(index):
    now = time.time()
    last_vote = session.get("last_vote_time", 0)

    if now - last_vote < 10:
        emit("poll_update", {"options": live_poll["options"], "votes": live_poll["votes"], "message": "⏳ Voto ignorado: aguarde antes de votar novamente."})
        return

    session["last_vote_time"] = now

    if 0 <= index < len(live_poll["votes"]):
        live_poll["votes"][index] += 1
        emit("poll_update", {"options": live_poll["options"], "votes": live_poll["votes"]}, broadcast=True)


@socketio.on("submit_quiz")
def handle_quiz_submission(data):
    results = []
    corretas = 0
    erradas = 0

    for i, user_answer in enumerate(data):
        correct = user_answer in quiz_data[i]["answer"]
        if correct:
            corretas += 1
        else:
            erradas += 1
        results.append({"question": quiz_data[i]["question"], "correct": correct, "explanation": quiz_data[i]["explanation"]})

    # Atualiza estatísticas globais
    quiz_stats["corretas"] += corretas
    quiz_stats["erradas"] += erradas

    emit("quiz_results", results)
    emit("quiz_stats_update", quiz_stats, broadcast=True)


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True, allow_unsafe_werkzeug=True)
