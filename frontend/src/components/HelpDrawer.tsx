import { useState } from 'react'
import { Button, Drawer } from 'antd'
import { QuestionCircleOutlined } from '@ant-design/icons'
import { marked } from 'marked'
import { useNavigate } from 'react-router-dom'
import { HELP_CONTENT } from '../assets/helpContent'

interface Props {
  pageKey: string
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

export default function HelpDrawer({ pageKey }: Props) {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const help = HELP_CONTENT[pageKey]

  if (!help) return null

  const html = marked.parse(help.content) as string

  return (
    <>
      <style>{HELP_STYLES}</style>
      <Button
        size="small"
        icon={<QuestionCircleOutlined />}
        onClick={() => setOpen(true)}
        style={{
          position: 'fixed',
          bottom: 24,
          right: 24,
          zIndex: 1000,
          boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
        }}
      >
        使い方
      </Button>
      <Drawer
        title={help.title}
        placement="right"
        width={480}
        open={open}
        onClose={() => setOpen(false)}
        extra={
          <Button
            type="link"
            size="small"
            onClick={() => {
              setOpen(false)
              navigate('/help')
            }}
          >
            全体のヘルプを見る →
          </Button>
        }
        styles={{ body: { padding: '16px 24px' } }}
      >
        {/* content is authored internally — not user input */}
        <div className="help-markdown" dangerouslySetInnerHTML={{ __html: html }} />
      </Drawer>
    </>
  )
}
