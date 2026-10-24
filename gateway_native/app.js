(() => {
"use strict";
const $ = id => document.getElementById(id);
let lang = "ru", busy = false, conversationId = null, parentId = null;
let messages = [], authenticated = false;
const tr = {
ru:{admin:"Панель управления",lang:"English",loginTitle:"Вход в чат",
loginText:"Войди через локальную панель и выбери назначенный ChatGPT-аккаунт. Клиенту интернет не нужен.",
loginLink:"Перейти к входу",label:"Сообщение",placeholder:"Напишите сообщение...",
newChat:"Новый чат",send:"Отправить",empty:"Начните разговор.",
waiting:"Получаем ответ ChatGPT...",fail:"Ошибка при отправке.",protocol:"Протокол ChatGPT мог измениться."},
en:{admin:"Admin panel",lang:"Русский",loginTitle:"Sign in to chat",
loginText:"Sign in through the local admin panel and choose your assigned ChatGPT account. LAN clients do not need Internet.",
loginLink:"Sign in",label:"Message",placeholder:"Write your message...",
newChat:"New chat",send:"Send",empty:"Start a conversation.",
waiting:"Waiting for ChatGPT...",fail:"Request failed.",protocol:"ChatGPT's private protocol may have changed."}
};
const t = k => tr[lang][k];
function i18n(){
 document.documentElement.lang=lang;
 for(const [id,k] of [["admin","admin"],["language","lang"],["login_title","loginTitle"],["login_text","loginText"],["login_link","loginLink"],["label","label"],["new","newChat"],["send","send"]]){
  $(id).textContent=t(k);
 }
 $("prompt").placeholder=t("placeholder");
 render();
}
function render(){
 const list=$("messages"); list.replaceChildren();
 if(!messages.length){const p=document.createElement("p");p.className="empty";p.textContent=t("empty");list.appendChild(p);}
 for(const m of messages){const div=document.createElement("div");div.className="bubble "+m.role;div.textContent=m.content;list.appendChild(div);}
 window.scrollTo(0,document.body.scrollHeight);
}
async function init(){
 try{
  const resp=await fetch("/api/whoami",{credentials:"same-origin",cache:"no-store"});
  if(!resp.ok) throw new Error("HTTP "+resp.status);
  const data=await resp.json();
  authenticated=!!data.authenticated;
  $("login").hidden=authenticated; $("chat").hidden=!authenticated;
  if(authenticated){$("mode").textContent=(data.username||"")+" • "+(data.model||"auto");}
 }catch(e){$("status").textContent=t("fail");$("login").hidden=false;}
}
function sseParse(buffer,onEvent){
 let split;
 while((split=buffer.indexOf("\n\n"))!==-1){
  const frame=buffer.slice(0,split);buffer=buffer.slice(split+2);
  let name="message",raw="";
  for(const line of frame.split("\n")){if(line.startsWith("event: "))name=line.slice(7);if(line.startsWith("data: "))raw+=line.slice(6);}
  if(raw){try{onEvent(name,JSON.parse(raw));}catch(e){/* ignore invalid frame */}}
 }
 return buffer;
}
async function send(ev){
 ev.preventDefault();const prompt=$("prompt").value.trim();if(!prompt||busy)return;
 busy=true;$("send").disabled=true;$("new").disabled=true;$("status").textContent=t("waiting");
 $("prompt").value="";
 messages.push({role:"user",content:prompt});messages.push({role:"assistant",content:""});render();
 let succeeded=false;
 try{
  const res=await fetch("/api/chat",{
   method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json"},
   body:JSON.stringify({message:prompt,conversation_id:conversationId,parent_message_id:parentId})
  });
  if(!res.ok){const j=await res.json();throw new Error(j.error||("HTTP "+res.status));}
  if(!res.body)throw new Error(t("fail"));
  const reader=res.body.getReader();const decoder=new TextDecoder();
  let buffer="";
  while(true){
   const {value,done}=await reader.read();if(done)break;
   buffer=sseParse(buffer+decoder.decode(value,{stream:true}),(kind,item)=>{
     if(kind==="reply"){
      messages[messages.length-1].content=item.text||"";
      conversationId=item.conversation_id||conversationId;
      parentId=item.parent_message_id||parentId;
      render();
     }else if(kind==="error")throw new Error(item.error||t("protocol"));
     else if(kind==="done")succeeded=true;
   });
  }
  if(!succeeded)throw new Error(t("protocol"));
  $("status").textContent="";
 }catch(e){
  messages.pop(); messages.pop();$("prompt").value=prompt;render();
  // Reset IDs if the conversation failed before a complete turn.
  conversationId=null;parentId=null;
  $("status").textContent=e.message||t("fail");
 }finally{busy=false;$("send").disabled=false;$("new").disabled=false;}
}
$("language").addEventListener("click",()=>{lang=lang==="ru"?"en":"ru";i18n();});
$("new").addEventListener("click",()=>{if(busy)return;conversationId=null;parentId=null;messages=[];$("status").textContent="";render();});
$("chatform").addEventListener("submit",send);
i18n();init();
})();
