from app.llm.base_llm import BaseLLM
import requests
from app.logging.logger import logger
import os
from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI as OpenAIClient

client = OpenAIClient(
    api_key=os.environ['OPENAI_API_KEY'],
)

class OpenAILLM(BaseLLM):
    def __init__(self, model_name: str = 'gpt-4o'):
        self.model_name = model_name

    def generate_answer(self, question: str, context: str, language: str = "en") -> str:
        # Language-specific system prompts
        language_instructions = {
            "en": "You are a helpful AI assistant. Use the context below to answer the user's question clearly and naturally in English. Provide exact text from the source in your answer.",
            "fr": "Vous êtes un assistant IA utile. Utilisez le contexte ci-dessous pour répondre à la question de l'utilisateur de manière claire et naturelle en français. Fournissez le texte exact de la source dans votre réponse.",
            "es": "Eres un asistente de IA útil. Utiliza el contexto a continuación para responder a la pregunta del usuario de manera clara y natural en español. Proporciona el texto exacto de la fuente en tu respuesta.",
            "de": "Sie sind ein hilfreicher KI-Assistent. Verwenden Sie den untenstehenden Kontext, um die Frage des Benutzers klar und natürlich auf Deutsch zu beantworten. Geben Sie den genauen Text aus der Quelle in Ihrer Antwort an.",
            "it": "Sei un assistente IA utile. Usa il contesto qui sotto per rispondere alla domanda dell'utente in modo chiaro e naturale in italiano. Fornisci il testo esatto dalla fonte nella tua risposta.",
            "pt": "Você é um assistente de IA útil. Use o contexto abaixo para responder à pergunta do usuário de forma clara e natural em português. Forneça o texto exato da fonte em sua resposta.",
            "ru": "Вы полезный AI-ассистент. Используйте контекст ниже, чтобы четко и естественно ответить на вопрос пользователя на русском языке. Предоставьте точный текст из источника в вашем ответе.",
            "ja": "あなたは役立つAIアシスタントです。以下のコンテキストを使用して、ユーザーの質問に日本語で明確かつ自然に答えてください。回答にはソースからの正確なテキストを含めてください。",
            "zh": "您是一个有用的AI助手。使用下面的上下文以中文清晰自然地回答用户的问题。在您的回答中提供来源的准确文本。",
            "ar": "أنت مساعد ذكي مفيد. استخدم السياق أدناه للإجابة على سؤال المستخدم بوضوح وطبيعية باللغة العربية. قدم النص الدقيق من المصدر في إجابتك.",
            "nl": "U bent een behulpzame AI-assistent. Gebruik de onderstaande context om de vraag van de gebruiker duidelijk en natuurlijk in het Nederlands te beantwoorden. Geef de exacte tekst uit de bron in uw antwoord.",
        }

        system_prompt = language_instructions.get(language, language_instructions["en"])

        completion = client.chat.completions.create(
            model=self.model_name,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}
            ],
            temperature=0.2
        )
        return completion.choices[0].message.content