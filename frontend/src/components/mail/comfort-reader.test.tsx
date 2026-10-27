import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { ReadingPane } from './reading-pane';
import type { MailMessage } from '@/lib/mail-data';
const noop = () => {};
const message: MailMessage = {id:'test',threadId:'t',sender:'sender@example.test',senderName:'Sender',subject:'Subject',preview:'Preview',body:'Original content',accountId:'a',to:'reader@example.test',date:'26/10/2026',time:'10:00',isoDate:'2026-10-26T15:00:00Z',unread:true,starred:false,risk:'bajo',attachments:[],categories:[],aiSummary:'',aiAction:''};
describe('comfortable reader controls', () => {
 for (const expanded of [false, true]) it(`labels expanded=${expanded} without changing message content`, () => {
  const html = renderToStaticMarkup(<MemoryRouter><ReadingPane expanded={expanded} onToggleExpand={noop} message={message} thread={[]} onBack={noop} onToggleStar={noop} onArchive={noop} onDelete={noop} onRetry={noop} onRetryThread={noop} onOpenThread={noop} onLoadMoreThread={noop}/></MemoryRouter>);
  expect(html).toContain(expanded ? 'Volver a vista dividida' : 'Ampliar lectura');
  expect(html).toContain(`aria-pressed="${expanded}"`);
  expect(html).toContain(message.body);
  expect(html).toContain('150%');
 });
});
