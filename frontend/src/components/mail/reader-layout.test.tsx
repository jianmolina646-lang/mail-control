import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import {MemoryRouter} from 'react-router-dom';
import {MessageRow} from './message-list';
import {ReadingPane} from './reading-pane';
import type {MailMessage} from '@/lib/mail-data';
const message:MailMessage={id:'test',threadId:'thread',sender:'sender@example.test',senderName:'Remitente de prueba',subject:'Un asunto completo y legible',preview:'Vista previa independiente',body:'Contenido completo del correo de prueba.',accountId:'account',to:'reader@example.test',date:'15/10/2026',time:'10:00',isoDate:'2026-10-15T15:00:00Z',unread:true,starred:false,risk:'bajo',attachments:[],categories:[],aiSummary:'',aiAction:''};
const noop=()=>{};
describe('reading-first mail layout',()=>{
 it('renders sender, subject and preview separately and exposes selection',()=>{
  const html=renderToStaticMarkup(<MessageRow data={{message,threadCount:1}} selected checked={false} onOpen={noop} onToggleCheck={noop} onToggleStar={noop} onToggleRead={noop} onArchive={noop} onDelete={noop}/>);
  for(const value of ['mail-row-sender','mail-row-subject','mail-row-preview','aria-current="true"',message.subject,message.preview])expect(html).toContain(value);
 });
 it('renders subject, sender, date and reading controls without changing content',()=>{
  const html=renderToStaticMarkup(<MemoryRouter><ReadingPane message={message} thread={[]} onBack={noop} onToggleStar={noop} onArchive={noop} onDelete={noop} onRetry={noop} onRetryThread={noop} onOpenThread={noop} onLoadMoreThread={noop} onToggleExpand={noop}/></MemoryRouter>);
  for(const value of [message.body,message.subject,message.sender,message.date,'Solo texto','Tamaño de lectura','Ampliar lectura','150%'])expect(html).toContain(value);
 });
 it('shows a useful empty reader',()=>{
  const html=renderToStaticMarkup(<MemoryRouter><ReadingPane message={null} thread={[]} onBack={noop} onToggleStar={noop} onArchive={noop} onDelete={noop} onRetry={noop} onRetryThread={noop} onOpenThread={noop} onLoadMoreThread={noop}/></MemoryRouter>);
  expect(html).toContain('Selecciona un mensaje');
 });
});
