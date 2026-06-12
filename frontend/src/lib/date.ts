/**
 * 日付文字列をローカルタイムの日付として解釈するユーティリティ（issue #30）
 *
 * `parseISO("2026-06-12")` や `new Date("2026-06-12")` は UTC 00:00 として解釈され、
 * JST など UTC オフセットのある環境で表示・保存の往復に 1 日のずれを生む。
 * 日付のみを扱う箇所（Calendar / Gantt / Schedule）ではこの関数で統一する。
 */
export function parseLocalDate(value: string): Date {
  // "YYYY-MM-DD" でも "YYYY-MM-DDTHH:mm:ssZ" でも先頭 10 文字の日付部分を採用する
  const datePart = value.slice(0, 10)
  const [year, month, day] = datePart.split('-').map(Number)
  return new Date(year, month - 1, day)
}
