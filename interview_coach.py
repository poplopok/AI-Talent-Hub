import json
import os
from datetime import datetime
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

MODEL = "openai/gpt-4o-mini"

class InterviewLogger:
    def __init__(self, participant_name: str):
        self.participant_name = participant_name
        self.turns = []
        self.final_feedback = None
        self.turn_counter = 0

    def log_turn(self, agent_message: str, user_message: str, internal_thoughts: str):
        self.turn_counter += 1
        self.turns.append({
            "turn_id": self.turn_counter,
            "agent_visible_message": agent_message,
            "user_message": user_message,
            "internal_thoughts": internal_thoughts
        })

    def set_feedback(self, feedback: str):
        self.final_feedback = feedback

    def save(self, filename: str = "interview_log.json"):
        data = {
            "participant_name": self.participant_name,
            "turns": self.turns,
            "final_feedback": self.final_feedback
        }
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n[LOG] Сохранено в {filename}")


class ObserverAgent:
    def __init__(self):
        self.system_prompt = """Ты - Observer (наблюдатель) на техническом интервью. Твоя задача:
1. Анализировать ответы кандидата на точность и глубину
2. Выявлять ложные факты, галлюцинации и попытки уйти от темы
3. Оценивать уровень уверенности кандидата
4. Давать рекомендации Интервьюеру о следующих шагах

Отвечай ТОЛЬКО в формате JSON:
{
    "answer_quality": "excellent/good/weak/incorrect/off_topic/hallucination",
    "confidence_level": "high/medium/low",
    "factual_errors": ["список ошибок или пустой"],
    "recommendation": "краткая рекомендация для интервьюера",
    "adjust_difficulty": "increase/maintain/decrease",
    "candidate_asked_question": true/false,
    "candidate_question": "вопрос кандидата если есть"
}"""

    def analyze(self, conversation_history: list, current_answer: str, position: str, grade: str) -> dict:
        messages = [{"role": "system", "content": self.system_prompt}]
        context = f"Позиция: {position}, Грейд: {grade}\n\nИстория диалога:\n"
        for msg in conversation_history[-6:]:
            context += f"{msg['role']}: {msg['content']}\n"
        context += f"\nТекущий ответ кандидата: {current_answer}"
        messages.append({"role": "user", "content": context})
        
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.3
        )
        
        try:
            return json.loads(response.choices[0].message.content)
        except:
            return {
                "answer_quality": "good",
                "confidence_level": "medium",
                "factual_errors": [],
                "recommendation": "Продолжить интервью",
                "adjust_difficulty": "maintain",
                "candidate_asked_question": False,
                "candidate_question": ""
            }


class InterviewerAgent:
    def __init__(self, position: str, grade: str, experience: str):
        self.position = position
        self.grade = grade
        self.experience = experience
        self.difficulty = "medium"
        self.topics_covered = []
        self.correct_answers = []
        self.incorrect_answers = []
        self.system_prompt = f"""Ты - профессиональный технический интервьюер. 
Проводишь собеседование на позицию: {position}
Ожидаемый грейд: {grade}
Опыт кандидата: {experience}

Правила:
1. Задавай релевантные технические вопросы по одному
2. Адаптируй сложность под уровень ответов
3. Если кандидат говорит явную чушь - вежливо укажи на ошибку
4. Если кандидат задает вопрос - ответь на него, потом продолжи
5. НЕ повторяй вопросы, на которые уже получен ответ
6. При off-topic - возвращай к теме интервью
7. На "Стоп интервью" или "Стоп игра" - заверши беседу"""

    def generate_response(self, conversation_history: list, observer_analysis: dict) -> str:
        messages = [{"role": "system", "content": self.system_prompt}]
        
        instruction = f"""
Анализ Observer:
- Качество ответа: {observer_analysis.get('answer_quality', 'N/A')}
- Фактические ошибки: {observer_analysis.get('factual_errors', [])}
- Рекомендация: {observer_analysis.get('recommendation', '')}
- Сложность: {observer_analysis.get('adjust_difficulty', 'maintain')}
- Кандидат задал вопрос: {observer_analysis.get('candidate_asked_question', False)}
- Вопрос кандидата: {observer_analysis.get('candidate_question', '')}

Уже затронутые темы: {self.topics_covered}
Текущая сложность: {self.difficulty}

Сгенерируй следующую реплику интервьюера. Если кандидат задал вопрос - сначала ответь на него."""

        for msg in conversation_history:
            messages.append(msg)
        
        messages.append({"role": "system", "content": instruction})
        
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.7
        )
        
        return response.choices[0].message.content

    def get_greeting(self) -> str:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": "Начни интервью с приветствия и первого вопроса."}
        ]
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.7
        )
        return response.choices[0].message.content


class ManagerAgent:
    def __init__(self):
        self.system_prompt = """Ты - Hiring Manager, принимаешь финальное решение по кандидату.
Проанализируй всё интервью и выдай структурированный отчёт в формате:

## Вердикт (Decision)
- **Grade**: Junior / Middle / Senior
- **Hiring Recommendation**: Hire / No Hire / Strong Hire
- **Confidence Score**: 0-100%

## Анализ Hard Skills
### Confirmed Skills:
(список подтвержденных навыков)

### Knowledge Gaps:
(список пробелов с правильными ответами)

## Анализ Soft Skills & Communication
- **Clarity**: оценка ясности изложения
- **Honesty**: оценка честности
- **Engagement**: оценка вовлеченности

## Персональный Roadmap
(конкретные рекомендации что изучить)"""

    def generate_feedback(self, conversation_history: list, position: str, grade: str) -> str:
        messages = [{"role": "system", "content": self.system_prompt}]
        
        context = f"Позиция: {position}\nОжидаемый грейд: {grade}\n\nПолный лог интервью:\n"
        for msg in conversation_history:
            role = "Интервьюер" if msg["role"] == "assistant" else "Кандидат"
            context += f"{role}: {msg['content']}\n\n"
        
        messages.append({"role": "user", "content": context})
        
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.5
        )
        
        return response.choices[0].message.content


class InterviewCoach:
    def __init__(self, position: str, grade: str, experience: str, participant_name: str = "Смирнов Игорь Евгеньевич"):
        self.interviewer = InterviewerAgent(position, grade, experience)
        self.observer = ObserverAgent()
        self.manager = ManagerAgent()
        self.logger = InterviewLogger(participant_name)
        self.conversation_history = []
        self.position = position
        self.grade = grade
        self.is_finished = False

    def start(self) -> str:
        greeting = self.interviewer.get_greeting()
        self.conversation_history.append({"role": "assistant", "content": greeting})
        return greeting

    def process_input(self, user_input: str) -> str:
        if any(stop in user_input.lower() for stop in ["стоп интервью", "стоп игра"]):
            self.is_finished = True
            return self._finish_interview(user_input)
        
        if "давай фидбэк" in user_input.lower():
            feedback = self._get_interim_feedback()
            return feedback
        
        self.conversation_history.append({"role": "user", "content": user_input})
        
        observer_analysis = self.observer.analyze(
            self.conversation_history, 
            user_input,
            self.position,
            self.grade
        )
        
        internal_thoughts = self._format_internal_thoughts(observer_analysis)
        
        if observer_analysis.get("adjust_difficulty") == "increase":
            self.interviewer.difficulty = "hard"
        elif observer_analysis.get("adjust_difficulty") == "decrease":
            self.interviewer.difficulty = "easy"
        
        response = self.interviewer.generate_response(
            self.conversation_history,
            observer_analysis
        )
        
        self.conversation_history.append({"role": "assistant", "content": response})
        
        prev_agent_message = self.conversation_history[-3]["content"] if len(self.conversation_history) >= 3 else ""
        self.logger.log_turn(prev_agent_message, user_input, internal_thoughts)
        
        return response

    def _format_internal_thoughts(self, analysis: dict) -> str:
        thoughts = []
        thoughts.append(f"[Observer]: Качество ответа: {analysis.get('answer_quality', 'N/A')}")
        
        if analysis.get("factual_errors"):
            thoughts.append(f"[Observer]: ВНИМАНИЕ! Обнаружены ошибки: {', '.join(analysis['factual_errors'])}")
        
        if analysis.get("answer_quality") == "hallucination":
            thoughts.append("[Observer]: Кандидат выдает ложную информацию. Необходимо корректно указать на ошибку.")
        
        if analysis.get("answer_quality") == "off_topic":
            thoughts.append("[Observer]: Кандидат уходит от темы. Нужно вернуть к интервью.")
        
        if analysis.get("candidate_asked_question"):
            thoughts.append(f"[Observer]: Кандидат задал вопрос: {analysis.get('candidate_question', '')}")
            thoughts.append("[Interviewer]: Нужно ответить на вопрос кандидата, затем продолжить.")
        
        thoughts.append(f"[Interviewer]: Рекомендация - {analysis.get('recommendation', 'продолжить')}. Сложность: {analysis.get('adjust_difficulty', 'maintain')}")
        
        return " ".join(thoughts)

    def _get_interim_feedback(self) -> str:
        messages = [
            {"role": "system", "content": """Ты - Hiring Manager. Дай краткий промежуточный фидбэк по текущему ходу интервью.
Формат:
- Что идет хорошо
- Над чем стоит поработать
- Рекомендация как продолжить

После фидбэка предложи продолжить интервью."""},
            {"role": "user", "content": f"Позиция: {self.position}, Грейд: {self.grade}\n\nТекущий диалог:\n" + 
             "\n".join([f"{'Интервьюер' if m['role']=='assistant' else 'Кандидат'}: {m['content']}" for m in self.conversation_history])}
        ]
        response = client.chat.completions.create(model=MODEL, messages=messages, temperature=0.5)
        feedback = response.choices[0].message.content
        
        self.conversation_history.append({"role": "assistant", "content": feedback})
        return feedback

    def _finish_interview(self, user_input: str) -> str:
        feedback = self.manager.generate_feedback(
            self.conversation_history,
            self.position,
            self.grade
        )
        
        self.logger.log_turn(
            self.conversation_history[-1]["content"] if self.conversation_history else "",
            user_input,
            "[Manager]: Генерирую финальный отчет на основе всего интервью."
        )
        self.logger.set_feedback(feedback)
        self.logger.save()
        
        return feedback


def main():
    print("=" * 60)
    print("Multi-Agent Interview Coach")
    print("=" * 60)
    
    print("\nИнициализация системы...")
    position = input("Позиция (например, Backend Developer): ").strip() or "Backend Developer"
    grade = input("Грейд (Junior/Middle/Senior): ").strip() or "Junior"
    experience = input("Опыт кандидата: ").strip() or "Пет-проекты"
    
    coach = InterviewCoach(position, grade, experience)
    
    print("\n" + "=" * 60)
    greeting = coach.start()
    print(f"\n[Интервьюер]: {greeting}")
    
    while not coach.is_finished:
        print()
        user_input = input("[Вы]: ").strip()
        if not user_input:
            continue
        
        response = coach.process_input(user_input)
        print(f"\n[Интервьюер]: {response}")
    
    print("\n" + "=" * 60)
    print("Интервью завершено. Лог сохранен в interview_log.json")


if __name__ == "__main__":
    main()
