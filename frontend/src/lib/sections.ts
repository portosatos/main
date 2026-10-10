// Sections of the menu (SPEC §6.4); their pages come with later steps.
export const sections = [
  { to: "/", label: "Дашборд" },
  { to: "/upload", label: "Загрузка" },
  { to: "/devices", label: "Устройства" },
  { to: "/goals", label: "Цели" },
  { to: "/recommendations", label: "Рекомендации" },
  { to: "/rules", label: "Правила" },
  { to: "/settings", label: "Настройки" },
] as const;
