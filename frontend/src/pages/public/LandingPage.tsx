import { useEffect } from "react";

import { applySeo } from "../../seo";

export default function LandingPage() {
  useEffect(() => {
    applySeo({
      title: "Asya — персональный AI-ассистент",
      description:
        "Asya помогает с задачами, документами и ежедневными workflow. Запросите инвайт и подключитесь к закрытому раннему доступу.",
      path: "/",
    });
  }, []);

  return (
    <section className="page public-page" aria-label="Главная страница Asya">
      <h1 className="page__title">Asya</h1>
      <p>
        Персональный AI-ассистент для людей, которым нужен один рабочий центр: чаты, документы,
        интеграции и регулярные брифинги.
      </p>
      <h2>Для кого</h2>
      <p>Для founders, product/ops специалистов, небольших команд и тех, кто ведёт много процессов параллельно.</p>
      <h2>Как подключиться</h2>
      <p>
        Сейчас доступ работает по инвайтам. Оставьте заявку, коротко опишите свой сценарий, и мы
        вернёмся с решением по доступу.
      </p>
      <p>
        <a className="chat-action-button public-cta" href="/request-access">
          Запросить инвайт
        </a>
      </p>
    </section>
  );
}
