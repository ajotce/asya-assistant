import { FormEvent, useEffect, useState } from "react";

import { createDocumentTemplate, deleteDocumentTemplate, fillDocumentTemplate, listDocumentTemplates } from "../api/client";
import type { DocumentTemplate, GeneratedDocumentFile } from "../types/api";

export default function TemplatesPage() {
  const [items, setItems] = useState<DocumentTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("Гарантия Geely");
  const [provider, setProvider] = useState<"google_drive" | "yandex_disk" | "onedrive">("google_drive");
  const [fileId, setFileId] = useState("templates/geely-guarantee.docx");
  const [outputFormat, setOutputFormat] = useState<"docx" | "pdf" | "both">("both");

  const [fillTemplateId, setFillTemplateId] = useState("");
  const [fillValuesJson, setFillValuesJson] = useState('{"vin":"1HGCM82633A004352","client_name":"Иван Иванов"}');
  const [generatedFiles, setGeneratedFiles] = useState<GeneratedDocumentFile[]>([]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await listDocumentTemplates();
      setItems(data);
      if (!fillTemplateId && data[0]) {
        setFillTemplateId(data[0].id);
      }
    } catch (loadError) {
      setError(getErrorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      await createDocumentTemplate({
        name,
        description: "Шаблон документа",
        provider,
        file_id: fileId,
        fields: [
          { key: "vin", label: "VIN", type: "vin", required: true },
          { key: "client_name", label: "ФИО клиента", type: "text", required: true },
          { key: "passport_number", label: "Паспорт", type: "passport_number", required: false },
        ],
        output_settings: {
          format: outputFormat,
          filename: "geely-warranty",
        },
      });
      await load();
    } catch (createError) {
      setError(getErrorMessage(createError));
    }
  }

  async function handleDelete(id: string) {
    if (!window.confirm("Удалить шаблон?")) {
      return;
    }
    setError(null);
    try {
      await deleteDocumentTemplate(id);
      await load();
    } catch (deleteError) {
      setError(getErrorMessage(deleteError));
    }
  }

  async function handleFill(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!fillTemplateId) {
      setError("Выберите шаблон.");
      return;
    }
    setError(null);
    setGeneratedFiles([]);
    try {
      const parsed = JSON.parse(fillValuesJson) as Record<string, string>;
      const response = await fillDocumentTemplate(fillTemplateId, parsed);
      setGeneratedFiles(response.files);
    } catch (fillError) {
      setError(getErrorMessage(fillError));
    }
  }

  return (
    <section className="page" aria-label="Шаблоны документов">
      <h2 className="page__title">Шаблоны</h2>
      {loading ? <p className="status-text">Загрузка...</p> : null}
      {error ? <p className="status-text status-text--error">{error}</p> : null}

      <form className="settings-form" onSubmit={(e) => void handleCreate(e)}>
        <label className="settings-form__field">
          Название
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="settings-form__field">
          Provider
          <select value={provider} onChange={(e) => setProvider(e.target.value as typeof provider)}>
            <option value="google_drive">Google Drive</option>
            <option value="yandex_disk">Yandex.Disk</option>
            <option value="onedrive">OneDrive</option>
          </select>
        </label>
        <label className="settings-form__field">
          File ID
          <input value={fileId} onChange={(e) => setFileId(e.target.value)} />
        </label>
        <label className="settings-form__field">
          Output format
          <select value={outputFormat} onChange={(e) => setOutputFormat(e.target.value as typeof outputFormat)}>
            <option value="docx">DOCX</option>
            <option value="pdf">PDF</option>
            <option value="both">Both</option>
          </select>
        </label>
        <button className="settings-form__submit" type="submit">Создать шаблон</button>
      </form>

      <ul className="chat-sidebar__list">
        {items.map((item) => (
          <li key={item.id} className="chat-sidebar__item">
            <span>{item.name} ({item.provider})</span>
            <button className="chat-edit-button" type="button" onClick={() => void handleDelete(item.id)}>Удалить</button>
          </li>
        ))}
      </ul>

      <form className="settings-form" onSubmit={(e) => void handleFill(e)}>
        <label className="settings-form__field">
          Шаблон
          <select value={fillTemplateId} onChange={(e) => setFillTemplateId(e.target.value)}>
            <option value="">Выберите...</option>
            {items.map((item) => (
              <option key={item.id} value={item.id}>{item.name}</option>
            ))}
          </select>
        </label>
        <label className="settings-form__field">
          Values JSON
          <textarea value={fillValuesJson} onChange={(e) => setFillValuesJson(e.target.value)} rows={4} />
        </label>
        <button className="settings-form__submit" type="submit">Заполнить</button>
      </form>

      {generatedFiles.length > 0 ? (
        <div>
          <p className="status-text">Сгенерированные файлы:</p>
          {generatedFiles.map((file) => (
            <button
              key={file.filename}
              type="button"
              className="chat-action-button"
              onClick={() => downloadGeneratedFile(file)}
            >
              Скачать {file.filename}
            </button>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function downloadGeneratedFile(file: GeneratedDocumentFile) {
  const binary = Uint8Array.from(atob(file.content_base64), (c) => c.charCodeAt(0));
  const blob = new Blob([binary], { type: file.content_type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = file.filename;
  a.click();
  URL.revokeObjectURL(url);
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "Ошибка запроса";
}
