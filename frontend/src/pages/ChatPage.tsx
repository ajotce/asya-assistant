import { FormEvent, useState } from "react";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
}

const initialMessages: ChatMessage[] = [
  { id: "assistant-welcome", role: "assistant", text: "Привет! Я Asya. Напишите сообщение, чтобы начать диалог." },
];

export default function ChatPage() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    if (!text) {
      return;
    }

    setMessages((prev) => [
      ...prev,
      { id: `user-${Date.now()}`, role: "user", text },
      {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        text: "Streaming API подключается на следующем этапе UI. Backend уже готов.",
      },
    ]);
    setInput("");
  }

  return (
    <section className="page" aria-label="Чат Asya">
      <h2 className="page__title">Чат</h2>
      <div className="chat-list">
        {messages.map((message) => (
          <article
            key={message.id}
            className={`chat-bubble ${message.role === "user" ? "chat-bubble--user" : "chat-bubble--assistant"}`}
          >
            <p className="chat-bubble__role">{message.role === "user" ? "Вы" : "Asya"}</p>
            <p className="chat-bubble__text">{message.text}</p>
          </article>
        ))}
      </div>

      <form className="chat-form" onSubmit={handleSubmit}>
        <label className="sr-only" htmlFor="chat-input">
          Сообщение
        </label>
        <textarea
          id="chat-input"
          className="chat-form__input"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          rows={3}
          placeholder="Введите сообщение"
        />
        <button type="submit" className="chat-form__submit">
          Отправить
        </button>
      </form>
    </section>
  );
}
