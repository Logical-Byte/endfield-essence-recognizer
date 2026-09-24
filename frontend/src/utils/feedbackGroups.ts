/**
 * 反馈渠道配置。
 *
 * 群号与邀请链接属于运营配置而非界面逻辑，集中放在这里，
 * 换群时不必翻组件模板。
 */

export interface FeedbackGroup {
  name: string
  link: string
}

export const QQ_FEEDBACK_GROUPS: readonly FeedbackGroup[] = [
  {
    name: '①群：486622964',
    link: 'https://qm.qq.com/cgi-bin/qm/qr?k=1xqRp7JwQHwGswa-8_SMFuAsRYYRnF8J',
  },
  {
    name: '②群：1082880855',
    link: 'https://qm.qq.com/cgi-bin/qm/qr?k=qAmvmHCc3HuESiJhZVe6Ytgj7foOxXx9',
  },
  {
    name: '③群：1042417974',
    link: 'https://qm.qq.com/cgi-bin/qm/qr?k=-GykJWhnZEN5F2aZ1nrVd3xs9RGkMBI2',
  },
]
