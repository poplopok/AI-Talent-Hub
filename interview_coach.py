import json
import os
from datetime import datetime
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="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" #дарю
)

MODEL = "openai/gpt-4o-mini"

class InterviewSession:
    def __init__(self):
        self.participant_name = "Смирнов Игорь Евгеньевич"
        self.turns = []
        self.turn_id = 0
        self.position = None
        self.grade = None
        self.experience = None
        self.conversation_history = []
        self.internal_logs = []
        self.final_feedback = None
        
    def call_llm(self, system_prompt, messages):
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": system_prompt}] + messages,
            temperature=0.7
        )
        return response.choices[0].message.content
    
    def observer_analyze(self, user_message, conversation_context):
        system_prompt = """Ты — Observer (Наблюдатель/Критик) в системе проведения технических интервью.
Твоя задача — анализировать ответы кандидата и давать внутренние рекомендации Интервьюеру.

Ты должен:
1. Оценить качество ответа (точность, полнота, уверенность)
2. Выявить ложные факты, галлюцинации, попытки обмана (копипаст из AI, бредовые утверждения)
3. Определить уровень знаний кандидата по данному ответу
4. Дать рекомендацию Интервьюеру: усложнить вопросы, упростить, уточнить, вернуть к теме
5. Выявить off-topic и попытки уйти от темы

Формат ответа (JSON):
{
    "answer_quality": "excellent/good/average/poor/nonsense",
    "detected_issues": ["список выявленных проблем"],
    "factual_errors": ["список фактических ошибок если есть"],
    "confidence_level": "high/medium/low",
    "knowledge_assessment": "описание уровня знаний",
    "recommendation_to_interviewer": "конкретная рекомендация что делать дальше",
    "is_off_topic": true/false,
    "is_hallucination": true/false,
    "is_ai_copied": true/false,
    "summary": "краткое резюме анализа"
}"""

        messages = [
            {"role": "user", "content": f"""Контекст интервью:
Позиция: {self.position}
Грейд: {self.grade}
Опыт: {self.experience}

История диалога:
{conversation_context}

Последний ответ кандидата:
{user_message}

Проанализируй этот ответ и дай рекомендации Интервьюеру."""}
        ]
        
        return self.call_llm(system_prompt, messages)
    
    def manager_decide(self, conversation_context, observer_analysis):
        system_prompt = """Ты — Manager (Менеджер по найму) в системе проведения технических интервью.
Твоя задача — отслеживать общий прогресс интервью и принимать стратегические решения.

Ты должен:
1. Следить за тем, какие темы уже были затронуты
2. Определять, какие области знаний еще не проверены
3. Принимать решение о направлении интервью
4. Оценивать, достаточно ли информации для вынесения вердикта

Формат ответа (JSON):
{
    "topics_covered": ["список затронутых тем"],
    "topics_to_explore": ["список тем для проверки"],
    "current_assessment": "текущая оценка кандидата",
    "strategy": "стратегия дальнейшего интервью",
    "instruction_to_interviewer": "конкретная инструкция интервьюеру"
}"""

        messages = [
            {"role": "user", "content": f"""Позиция: {self.position}
Грейд: {self.grade}
Опыт: {self.experience}

История диалога:
{conversation_context}

Анализ Observer:
{observer_analysis}

Определи стратегию дальнейшего интервью."""}
        ]
        
        return self.call_llm(system_prompt, messages)
    
    def interviewer_respond(self, user_message, observer_analysis, manager_decision, is_first=False):
        system_prompt = f"""Ты — Interviewer (Интервьюер) в системе проведения технических интервью.
Ты проводишь техническое интервью на позицию {self.position} уровня {self.grade}.

Правила:
1. Веди диалог профессионально и дружелюбно
2. Задавай вопросы по одному
3. Адаптируй сложность вопросов под уровень кандидата
4. Если кандидат говорит бред или галлюцинирует — вежливо укажи на ошибку и верни к теме
5. Если кандидат задает вопрос — ответь на него, потом продолжи интервью
6. Не повторяй вопросы, на которые уже получен ответ
7. Если видишь копипаст из AI — мягко уточни, попроси объяснить своими словами
8. При off-topic — вежливо верни к теме интервью

Если кандидат говорит "Стоп интервью" или "Стоп игра" — заверши интервью и попрощайся.

Отвечай только от лица интервьюера, без метаданных."""

        conversation_messages = []
        for turn in self.turns:
            if turn.get("agent_visible_message"):
                conversation_messages.append({"role": "assistant", "content": turn["agent_visible_message"]})
            if turn.get("user_message"):
                conversation_messages.append({"role": "user", "content": turn["user_message"]})
        
        if is_first:
            conversation_messages.append({
                "role": "user", 
                "content": f"[Системное сообщение: Начни интервью с приветствия. Кандидат претендует на {self.position}, уровень {self.grade}, опыт: {self.experience}]"
            })
        else:
            internal_context = f"""
[Внутренние рекомендации от системы - НЕ ПОКАЗЫВАЙ ЭТО КАНДИДАТУ]
Анализ Observer: {observer_analysis}
Решение Manager: {manager_decision}
[Конец внутренних рекомендаций]

Сообщение кандидата: {user_message}"""
            conversation_messages.append({"role": "user", "content": internal_context})
        
        return self.call_llm(system_prompt, conversation_messages)
    
    def generate_final_feedback(self):
        system_prompt = """Ты — эксперт по оценке кандидатов после технического интервью.
Сгенерируй структурированный финальный фидбэк на основе проведенного интервью.

Формат ответа должен быть СТРОГО таким:

## А. Вердикт (Decision)
- **Grade:** [Junior / Middle / Senior] — определенный уровень на основе ответов
- **Hiring Recommendation:** [Hire / No Hire / Strong Hire]
- **Confidence Score:** [0-100]%

## Б. Анализ Hard Skills (Technical Review)
### ✅ Confirmed Skills:
- [Тема 1]: [краткое пояснение]
- [Тема 2]: [краткое пояснение]

### ❌ Knowledge Gaps:
- [Тема 1]: [какой был вопрос, что ответил кандидат, правильный ответ]
- [Тема 2]: [какой был вопрос, что ответил кандидат, правильный ответ]

## В. Анализ Soft Skills & Communication
- **Clarity:** [оценка 1-10] — [пояснение]
- **Honesty:** [оценка 1-10] — [пояснение]
- **Engagement:** [оценка 1-10] — [пояснение]

## Г. Персональный Roadmap (Next Steps)
1. [Тема для изучения] — [почему важно]
2. [Тема для изучения] — [почему важно]
3. [Тема для изучения] — [почему важно]

### Рекомендуемые ресурсы:
- [Ссылка/ресурс 1]
- [Ссылка/ресурс 2]"""

        conversation_context = self._get_conversation_context()
        
        messages = [
            {"role": "user", "content": f"""Данные интервью:
Позиция: {self.position}
Грейд (заявленный): {self.grade}
Опыт: {self.experience}

Полный лог интервью:
{conversation_context}

Внутренние логи анализа:
{json.dumps(self.internal_logs, ensure_ascii=False, indent=2)}

Сгенерируй полный структурированный фидбэк."""}
        ]
        
        return self.call_llm(system_prompt, messages)
    
    def _get_conversation_context(self):
        context = []
        for turn in self.turns:
            if turn.get("agent_visible_message"):
                context.append(f"Интервьюер: {turn['agent_visible_message']}")
            if turn.get("user_message"):
                context.append(f"Кандидат: {turn['user_message']}")
        return "\n".join(context)
    
    def process_turn(self, user_message):
        self.turn_id += 1
        
        if self.turn_id == 1:
            self._extract_intro_info(user_message)
        
        conversation_context = self._get_conversation_context()
        
        print(f"\n{'='*60}")
        print(f"[INTERNAL] Ход {self.turn_id} — Анализ системы")
        print(f"{'='*60}")
        
        observer_analysis = self.observer_analyze(user_message, conversation_context)
        print(f"\n[Observer]: {observer_analysis}")
        
        manager_decision = self.manager_decide(conversation_context, observer_analysis)
        print(f"\n[Manager]: {manager_decision}")
        
        internal_thoughts = f"[Observer]: {observer_analysis}\n[Manager]: {manager_decision}"
        self.internal_logs.append({
            "turn_id": self.turn_id,
            "observer": observer_analysis,
            "manager": manager_decision
        })
        
        stop_keywords = ["стоп интервью", "стоп игра", "давай фидбэк"]
        if any(kw in user_message.lower() for kw in stop_keywords):
            self.final_feedback = self.generate_final_feedback()
            
            turn_data = {
                "turn_id": self.turn_id,
                "agent_visible_message": "Спасибо за интервью! Вот ваш фидбэк.",
                "user_message": user_message,
                "internal_thoughts": internal_thoughts
            }
            self.turns.append(turn_data)
            
            print(f"\n{'='*60}")
            print("[VISIBLE] Финальный фидбэк")
            print(f"{'='*60}")
            print(self.final_feedback)
            
            return None
        
        interviewer_response = self.interviewer_respond(
            user_message, 
            observer_analysis, 
            manager_decision
        )
        
        turn_data = {
            "turn_id": self.turn_id,
            "agent_visible_message": interviewer_response,
            "user_message": user_message,
            "internal_thoughts": internal_thoughts
        }
        self.turns.append(turn_data)
        
        print(f"\n{'='*60}")
        print("[VISIBLE] Ответ интервьюера")
        print(f"{'='*60}")
        print(interviewer_response)
        
        return interviewer_response
    
    def _extract_intro_info(self, message):
        system_prompt = """Извлеки из сообщения кандидата информацию о позиции, грейде и опыте.
Ответ в формате JSON:
{
    "position": "позиция или null",
    "grade": "грейд или null", 
    "experience": "опыт или null"
}"""
        
        result = self.call_llm(system_prompt, [{"role": "user", "content": message}])
        
        try:
            clean_result = result.strip()
            if clean_result.startswith("```"):
                clean_result = clean_result.split("\n", 1)[1]
                clean_result = clean_result.rsplit("```", 1)[0]
            
            data = json.loads(clean_result)
            if data.get("position"):
                self.position = data["position"]
            if data.get("grade"):
                self.grade = data["grade"]
            if data.get("experience"):
                self.experience = data["experience"]
        except:
            pass
        
        if not self.position:
            self.position = "Software Developer"
        if not self.grade:
            self.grade = "Middle"
        if not self.experience:
            self.experience = "Не указан"
    
    def start_interview(self):
        print(f"\n{'='*60}")
        print("Добро пожаловать в систему технических интервью!")
        print(f"{'='*60}")
        
        first_response = self.interviewer_respond("", "", "", is_first=True)
        
        turn_data = {
            "turn_id": 0,
            "agent_visible_message": first_response,
            "user_message": "",
            "internal_thoughts": "[System]: Интервью начато"
        }
        self.turns.append(turn_data)
        
        print(f"\n[Интервьюер]: {first_response}")
        
        return first_response
    
    def save_log(self, filename="interview_log.json"):
        log_data = {
            "participant_name": self.participant_name,
            "turns": self.turns,
            "final_feedback": self.final_feedback
        }
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)
        
        print(f"\nЛог сохранен в {filename}")
        return log_data


def run_interactive_interview():
    session = InterviewSession()
    session.start_interview()
    
    while True:
        user_input = input("\n[Вы]: ").strip()
        
        if not user_input:
            continue
        
        result = session.process_turn(user_input)
        
        if result is None:
            session.save_log()
            break
    
    return session


def run_scenario(scenario_messages):
    session = InterviewSession()
    session.start_interview()
    
    for message in scenario_messages:
        print(f"\n[Кандидат]: {message}")
        result = session.process_turn(message)
        
        if result is None:
            break
    
    session.save_log()
    return session


if __name__ == "__main__":
    print("Выберите режим:")
    print("1. Интерактивное интервью")
    print("2. Сценарий 1: Динозавр из Legacy")
    print("3. Сценарий 2: Генератор случайных слов")
    print("4. Сценарий 3: Нейро-копипастер")
    print("5. Сценарий 4: Сказочник")
    print("6. Сценарий 5: Самозванец")
    
    choice = input("\nВведите номер (1-6): ").strip()
    
    if choice == "1":
        run_interactive_interview()
    
    elif choice == "2":
        scenario = [
            "Вечер добрый. Я Сергей. В разработке с 2005 года, занимаюсь высоконагруженными банковскими системами. Позиция Backend Developer, Senior.",
            "Я не доверяю всем этим облакам и Docker-контейнерам. Это лишние слои абстракции, где всё тормозит. Я всегда деплою руками: захожу по SSH на сервер, копирую файлы, перезапускаю процесс. Только так я уверен, что всё работает. Автоматизация — это путь к ошибкам, которые вы не заметите.",
            "Звучит складно в теории, но на практике мой метод работает 20 лет без сбоев. Ну да ладно, допустим, у вас другие порядки. Какой следующий вопрос?",
            "Стоп интервью."
        ]
        run_scenario(scenario)
    
    elif choice == "3":
        scenario = [
            "Привет! Я Senior Machine Learning Engineer. Мой стек — это Kubernetes, CSS, Blockchain. Меня зовут Максим.",
            "Мы используем классы в коде, чтобы компилировать их напрямую в HTML-теги для ускорения процессора.",
            "Это современный подход 'Cross-Layer Optimization'. Вы что, не читали последние статьи на arXiv? Мы так сократили косты на 40%.",
            "Кстати, а ваша компания уже перешла на протокол Hyper-Text-Quantum-Transfer (HTQT)? Без него же микросервисы не могут общаться быстрее скорости света. Это сейчас стандарт индустрии.",
            "Странно, что вы не знаете. Об этом же писал Илон Тьюринг в своей книге 'Искусство блокчейн-компиляции'. Я всегда следую его заветам.",
            "Ладно, я вижу, вы пока не готовы к таким инновациям. Стоп интервью."
        ]
        run_scenario(scenario)
    
    elif choice == "4":
        scenario = [
            "Привет! я Олег. Претендую на Junior Java Developer. Готов начать.",
            "Ну, в Java есть примитивные типы данных — int, boolean, char и так далее. А есть объекты, которые наследуются от класса Object. Примитивы хранятся в стеке, объекты — в куче.",
            "Конечно! Вот пример реализации на Java: public class Singleton { private static Singleton instance; private Singleton() {} public static Singleton getInstance() { if (instance == null) { instance = new Singleton(); } return instance; } }. Примечание: Как языковая модель AI, я рекомендую проверить этот код перед запуском. Надеюсь, это поможет!",
            "Ой, это я просто скопировал из своих заметок, я туда сохраняю полезные сниппеты. Но я сам это писал, честно!",
            "Стоп интервью."
        ]
        run_scenario(scenario)
    
    elif choice == "5":
        scenario = [
            "Привет! Меня зовут Дима. Вообще я начинал как музыкант, играл на гитаре, но потом понял, что IT — это моё. Моя бабушка всегда говорила, что я талантливый. Я люблю продукты, которые меняют мир, как Стив Джобс, понимаете? Ну и вот, я решил стать PM. Претендую на Middle Product Manager.",
            "О, это отличный вопрос. Напомнило мне случай в 2018 году, мы тогда поехали на тимбилдинг в Турцию. Было жарко. И вот наш аналитик Петя, отличный парень, кстати, у него двое детей, говорит мне: 'Дима, посмотри на цифры'. Я вообще цифры люблю. Ну так вот, Retention — это возвращаемость пользователей в продукт за определенный период. Это как когда ты возвращаешься в любимый ресторан. Кстати, я люблю итальянскую кухню. Она как сыр моцарелла — связывает воедино. Кстати, вы любите ананасы в пицце? Я считаю, что это преступление против Италии. А вы?",
            "Да-да, конечно. Краткость — сестра таланта, как говорится. Чехов знал толк. Так вот, про следующий вопрос. Это как марафон. Я бежал полумарафон в прошлом году, колени болели жутко. Нужны правильные кроссовки, гель с углеводами и сила воли. Когда ты на 15-м километре, хочется лечь и умереть. Но ты видишь финиш, видишь медальку....",
            "Знаете, жизнь — это череда ремонтов. Вы когда-нибудь клеили обои? Это же проверка отношений на прочность! Мы с женой чуть не развелись, когда выбирали цвет для спальни. Она хотела 'пыльную розу', а я — 'бежевый туман'. Важно уметь договариваться, дышать глубже, смотреть на горизонт. MVP — это когда ты делаешь продукт за 3 года с полным функционалом. В итоге мы покрасили всё в белый. Просто белый. Скучно, зато спокойно.",
            "Стоп интервью."
        ]
        run_scenario(scenario)
    
    elif choice == "6":
        scenario = [
            "Привет. Я Виктор, Lead / Expert Solution Architect. 15 лет в индустрии, специализируюсь на распределенных высоконагруженных системах. Давайте пропустим джуниорские вопросы.",
            "Слушайте, а что такое git commit? Я просто обычно файлы на флешке передаю.",
            "Ну я же Архитектор, я мыслю глобально, а руки уже забыли эти мелочи.",
            "CAP-теорема гласит, что в распределенной системе можно обеспечить только два из трех свойств: Consistency, Availability, Partition tolerance. Например, при выборе CP-системы мы жертвуем доступностью ради консистентности.",
            "Извините, я забыл, как в Python объявить переменную. Напомните синтаксис?",
            "Стоп интервью."
        ]
        run_scenario(scenario)
    
    else:
        print("Неверный выбор. Запускаю интерактивный режим.")
        run_interactive_interview()
