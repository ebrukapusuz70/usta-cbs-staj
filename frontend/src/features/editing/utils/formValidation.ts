/* Formlardaki zorunlu metin, pozitif sayı ve yıl kontrollerini yapar.
 * Hatalı veriyi API'ye gönderilmeden önce bildirir. */
import type { FormErrors } from "../types/editing";

export function requiredText(value: string, label: string, errors: FormErrors, key: string): string {
  const trimmed = value.trim();
  if (!trimmed) errors[key] = `${label} zorunludur.`;
  else if (trimmed.length > 100) errors[key] = `${label} en fazla 100 karakter olabilir.`;
  return trimmed;
}

export function operatorName(value: string, errors: FormErrors): string {
  const trimmed = requiredText(value, "İşlemi yapan operatör", errors, "operator_name");
  if (trimmed && trimmed.length < 2) {
    errors.operator_name = "İşlemi yapan operatör en az 2 karakter olmalıdır.";
  }
  return trimmed;
}

export function pipeCode(value: string, errors: FormErrors): string {
  const trimmed = requiredText(value, "Boru kodu", errors, "pipe_code");
  if (trimmed && !/^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$/.test(trimmed)) {
    errors.pipe_code = "Boru kodu yalnız harf, rakam ve bölümler arasında kısa çizgi içerebilir.";
  }
  return trimmed;
}

export function valveCode(value: string, errors: FormErrors): string {
  const trimmed = requiredText(value, "Vana kodu", errors, "valve_code");
  if (trimmed && !/^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$/.test(trimmed)) {
    errors.valve_code = "Vana kodu yalnız harf, rakam ve bölümler arasında kısa çizgi içerebilir.";
  }
  return trimmed;
}

export function positiveNumber(value: string, label: string, errors: FormErrors, key: string): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) errors[key] = `${label} sıfırdan büyük olmalıdır.`;
  return parsed;
}

export function validInstallYear(value: string, errors: FormErrors): number {
  const year = Number(value);
  const currentYear = new Date().getFullYear();
  if (!Number.isInteger(year) || year < 1900 || year > currentYear) {
    errors.install_year = `Döşeme yılı 1900–${currentYear} arasında olmalıdır.`;
  }
  return year;
}
