// SteamID64 tem exatamente 17 dígitos. Formato apenas — existência só a Steam
// sabe, e quem responde por ela é /api/users/{id}/profile.
export const isSteamId64 = (value: string) => /^\d{17}$/.test(value);
