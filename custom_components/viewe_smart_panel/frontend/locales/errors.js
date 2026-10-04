// Translate legacy server messages without rewriting user-entered names.
const messages = {
  "Профіль не знайдено": "Profile not found",
  "Профіль змінено в іншому вікні. Оновіть редактор": "This profile changed in another window. Refresh the editor",
  "Спочатку змініть або скасуйте призначення профілю панелям": "Change or remove panel assignments before deleting this profile",
  "Виберіть панель і застосований профіль": "Choose a panel and an applied profile",
  "Профіль несумісний із панеллю": "The profile is incompatible with this panel",
  "Інтеграція не завантажена": "The integration is not loaded",
  "Не вдалося зберегти конфігурацію. Перевірте сховище Home Assistant": "Could not save the configuration. Check Home Assistant storage",
  "Невідомий шаблон сторінки": "Unknown page template",
  "Тип керування не підтримується вибраним світлом": "The selected light does not support this control type",
  "Час має бути у форматі HH:MM": "Time must use the HH:MM format",
  "Очікується профіль": "Expected a profile",
  "Профіль повинен мати ID та назву до 128 символів": "A profile needs an ID and a name of up to 128 characters",
  "Профіль може містити до 64 сторінок": "A profile can contain up to 64 pages",
  "ID сторінок мають бути унікальними": "Page IDs must be unique",
  "Сторінка повинна мати назву до 128 символів": "A page needs a name of up to 128 characters",
  "Некоректна видимість або режим назви": "Invalid visibility or name mode",
  "Невідповідна сутність сторінки": "Incorrect entity domain for the page",
  "Невідомий тип освітлення": "Unknown lighting type",
  "Некоректні налаштування парасолі": "Invalid umbrella settings",
  "Ймовірність має бути від 0 до 100%": "Probability must be between 0 and 100%",
  "Кінець вікна прогнозу має бути після початку": "The forecast window must end after it starts",
  "Потрібно додати або показати хоча б одну сторінку": "Add or show at least one page before applying"
};

export function englishError(message, fallback) {
  if(messages[message])return messages[message];
  const incompatible="Профіль несумісний із панелями: ";
  if(message.startsWith(incompatible))return "Profile incompatible with panels: "+message.slice(incompatible.length);
  const binding="Виберіть наявну сутність для сторінки «";
  if(message.startsWith(binding))return "Choose an existing entity for page: "+message.slice(binding.length).replace(/»$/, "");
  return /[\u0400-\u04ff]/.test(message) ? fallback : message;
}
