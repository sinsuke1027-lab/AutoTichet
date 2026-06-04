import { Anchor, Typography } from 'antd'
import { marked } from 'marked'
import { FULL_GUIDE_SECTIONS } from '../../assets/helpContent'

const SECTION_IDS: Record<string, string> = {
  dashboard: 'help-dashboard',
  tasks: 'help-tasks',
  projects: 'help-projects',
  board: 'help-board',
  calendar: 'help-calendar',
  gantt: 'help-gantt',
  schedule: 'help-schedule',
  workload: 'help-workload',
  templates: 'help-templates',
  import: 'help-import',
  mypage: 'help-mypage',
  admin: 'help-admin',
}

const HELP_STYLES = `
  .help-markdown h2 { font-size: 15px; font-weight: 600; margin: 0 0 10px; }
  .help-markdown h3 { font-size: 13px; font-weight: 600; margin: 14px 0 6px; color: #555; }
  .help-markdown p { margin: 0 0 8px; line-height: 1.75; font-size: 13px; color: #333; }
  .help-markdown ul, .help-markdown ol { padding-left: 18px; margin: 0 0 8px; font-size: 13px; }
  .help-markdown li { margin-bottom: 4px; line-height: 1.65; }
  .help-markdown table { width: 100%; border-collapse: collapse; margin: 8px 0 12px; font-size: 13px; }
  .help-markdown th { background: #fafafa; padding: 6px 10px; border: 1px solid #e8e8e8; text-align: left; font-weight: 600; }
  .help-markdown td { padding: 6px 10px; border: 1px solid #e8e8e8; }
  .help-markdown strong { font-weight: 600; }
  .help-markdown code { background: #f5f5f5; padding: 1px 5px; border-radius: 3px; font-size: 12px; }
`

export default function HelpPage() {
  return (
    <div style={{ display: 'flex', gap: 32, alignItems: 'flex-start' }}>
      <style>{HELP_STYLES}</style>

      <div style={{ flex: 1, minWidth: 0 }}>
        <Typography.Title level={3} style={{ marginBottom: 4 }}>
          ヘルプ
        </Typography.Title>
        <Typography.Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>
          AutoTicket の各画面・機能の使い方をまとめています。
        </Typography.Text>

        {FULL_GUIDE_SECTIONS.map((section) => {
          const html = marked.parse(section.content) as string
          return (
            <div
              key={section.key}
              id={SECTION_IDS[section.key]}
              style={{ marginBottom: 40, scrollMarginTop: 16 }}
            >
              <div
                style={{
                  borderLeft: '4px solid #1677ff',
                  paddingLeft: 12,
                  marginBottom: 12,
                }}
              >
                <Typography.Title level={4} style={{ margin: 0 }}>
                  {section.title}
                </Typography.Title>
              </div>
              {/* content is authored internally — not user input */}
              <div
                className="help-markdown"
                style={{ paddingLeft: 4 }}
                dangerouslySetInnerHTML={{ __html: html }}
              />
            </div>
          )
        })}
      </div>

      <div style={{ width: 200, flexShrink: 0, position: 'sticky', top: 16 }}>
        <Anchor
          affix={false}
          items={FULL_GUIDE_SECTIONS.map((section) => ({
            key: section.key,
            href: `#${SECTION_IDS[section.key]}`,
            title: section.title.replace('の使い方', ''),
          }))}
        />
      </div>
    </div>
  )
}
