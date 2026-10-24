(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  let messages = [], busy = false, lang = "ru", configured = false;
  const strings = {
    ru: {
      loginTitle:"Вход в чат", intro:"Независимый чат на официальном OpenAI API. Не использует закрытый gateway.",
      pass:"Пароль чата", signIn:"Войти", signOut:"Выйти", admin:"Админ-панель",
      prompt:"Сообщение", placeholder:"Напиши сообщение...", send:"Отправить", clear:"Новый чат",
      empty:"Задай вопрос. Переписка находится только в текущей вкладке и исчезнет при обновлении.",
      waiting:"Ожидаем ответ...", noKey:"API-ключ не задан на сервере. Чат пока не сможет отвечать.",
      error:"Ошибка соединения.", label:"English"
    },
    en: {
      loginTitle:"Chat login", intro:"Independent chat using the official OpenAI API. No opaque legacy gateway.",
      pass:"Chat password", signIn:"Sign in", signOut:"Sign out", admin:"Admin panel",
      prompt:"Message", placeholder:"Write a message...", send:"Send", clear:"New chat",
      empty:"Ask a question. Messages stay in this browser tab and disappear when you refresh.",
      waiting:"Waiting for response...", noKey:"The server has no API key configured, so chat cannot reply yet.",
      error:"Connection error.", label:"Русский"
    }
  };
  function t(k){return strings[lang][k];}
  function translate(){
    document.documentElement.lang=lang;
    for (const [id,k] of [["login-title","loginTitle"],["intro","intro"],["password-label","pass"],["login-button","signIn"],["logout","signOut"],["admin-link","admin"],["prompt-label","prompt"],["send","send"],["clear","clear"],["empty-message","empty"],["lang","label"]]){
      $(id).textContent=t(k);
    }
    $("prompt").placeholder=t("placeholder");
    if (!configured && !$("chat").hidden) $("status").textContent=t("noKey");
  }
  async function call(path, data){
    const res=await fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},credentials:"same-origin",body:JSON.stringify(data)});
    const result=await res.json();
    if(!res.ok)throw new Error(result.error||("HTTP "+res.status));
    return result;
  }
  function showChat(auth){
    $("login").hidden=auth;
    $("chat").hidden=!auth;
    $("logout").hidden=!auth;
    if(auth&&!configured)$("status").textContent=t("noKey");
  }
  function render(){
    const box=$("messages");
    box.replaceChildren();
    if(!messages.length){const hint=document.createElement("p");hint.className="hint";hint.id="empty-message";hint.textContent=t("empty");box.append(hint);}
    for(const msg of messages){
      const elt=document.createElement("div");
      elt.className="bubble "+(msg.role==="user"?"user":"assistant");
      elt.textContent=msg.content; // never inject model output as HTML
      box.append(elt);
    }
    window.scrollTo(0,document.body.scrollHeight);
  }
  async function init(){
    translate();
    try{
      const res=await fetch("/api/session",{credentials:"same-origin"});
      if(!res.ok)throw new Error("status "+res.status);
      const data=await res.json();
      configured=data.configured;
      $("model").textContent=data.model;
      showChat(data.authenticated);
    }catch(err){$("status").textContent=t("error");}
  }
  $("lang").addEventListener("click",()=>{lang=lang==="ru"?"en":"ru";translate();render();});
  $("login-form").addEventListener("submit",async ev=>{
    ev.preventDefault();
    const btn=$("login-button");btn.disabled=true;
    try{
      await call("/api/login",{password:$("password").value});
      $("password").value="";$("status").textContent="";showChat(true);
    }catch(err){alert(err.message);}
    finally{btn.disabled=false;}
  });
  $("logout").addEventListener("click",async()=>{
    try{await call("/api/logout",{});}catch(err){$("status").textContent=err.message;return;}
    messages=[];render();showChat(false);
  });
  $("clear").addEventListener("click",()=>{if(busy)return;messages=[];render();$("status").textContent="";});
  $("chat-form").addEventListener("submit",async ev=>{
    ev.preventDefault();
    const value=$("prompt").value.trim();
    if(!value||busy)return;
    // Keep request within the backend limits.
    if(messages.length>=19)messages=messages.slice(-17);
    while(messages.reduce((n,m)=>n+m.content.length,0)+value.length>23000 && messages.length){
      messages.shift();
    }
    messages.push({role:"user",content:value});
    $("prompt").value="";render();busy=true;$("send").disabled=true;$("clear").disabled=true;$("status").textContent=t("waiting");
    try{
      const res=await call("/api/chat",{messages});
      messages.push({role:"assistant",content:res.reply});$("status").textContent="";
    }catch(err){
      messages.pop();$("prompt").value=value;$("status").textContent=err.message||t("error");
    }finally{busy=false;$("send").disabled=false;$("clear").disabled=false;render();}
  });
  init();
})();
