import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';

dayjs.extend(utc);
dayjs.extend(timezone);

const BEIJING_TZ = 'Asia/Shanghai';

export const formatBeijingTime = (
  value: string | null | undefined,
  format = 'YYYY-MM-DD HH:mm'
): string => {
  if (!value) return '--';

  // 如果字符串自带时区（Z 或 +08:00），直接按其含义转换到北京时区
  const hasTz = /[zZ]$|[+-]\d{2}:?\d{2}$/.test(value);
  let d = hasTz ? dayjs(value) : dayjs.utc(value);

  if (!d.isValid()) {
    // 兜底：尝试普通解析后再转时区
    d = dayjs(value);
  }

  return d.isValid() ? d.tz(BEIJING_TZ).format(format) : '--';
};

export const formatLatencySeconds = (latencyMs?: number | null): string => {
  if (latencyMs === null || latencyMs === undefined || Number.isNaN(latencyMs)) {
    return '-';
  }
  const seconds = latencyMs / 1000;
  const decimalPlaces = seconds >= 10 ? 1 : 2;
  return `${seconds.toFixed(decimalPlaces)}s`;
};

export const formatDurationMinutes = (
  seconds?: number | null,
  fallback = '--'
): string => {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) {
    return fallback;
  }
  if (seconds <= 0) {
    return '0.0';
  }
  const minutes = seconds / 60;
  return minutes.toFixed(1);
};

export default dayjs;
