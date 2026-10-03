const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const statusLabel = {offline:"Недоступна", pending:"Очікує підтвердження", applied:"Застосовано", error:"Помилка", timeout:"Немає підтвердження", incompatible:"Несумісна", unassigned:"Без профілю"};

class ViewePanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode:"open"});
    this.tab = "profiles";
    this.data = null;
    this.draft = null;
    this.pageId = null;
    this.dirty = false;
    this.busy = false;
    this.notice = "";
  }
  set hass(value) {
    this._hass = value;
    if (!this.data && !this.loading && this.isConnected) this.load();
  }
  connectedCallback() {
    this.render();
    if (this._hass && !this.data) this.load();
  }
  async api(action, payload={}) {
    return this._hass.callWS({type:"viewe_smart_panel/editor", action, payload});
  }
  async load() {
    this.loading = true;
    try { this.data = await this.api("get"); }
    catch (error) { this.notice = error.message || String(error); }
    finally { this.loading = false; this.render(); }
  }
  async perform(fn) {
    if (this.busy) return;
    this.busy = true;
    this.notice = "";
    this.render();
    try { await fn(); }
    catch (error) { this.notice = error.message || String(error); }
    finally { this.busy = false; this.render(); }
  }
  async save() {
    this.draft = await this.api("save", {profile:this.draft});
    this.dirty = false;
    this.data = await this.api("get");
    this.notice = "Профіль збережено. Панелі працюють із попередньою застосованою версією.";
  }
  leave() {
    return !this.dirty || window.confirm("Відкинути незбережені зміни?");
  }
  button(action, label, extra="", primary=false) {
    return `<button data-action="${action}" ${extra} class="${primary ? "primary" : ""}" ${this.busy ? "disabled" : ""}>${label}</button>`;
  }
  render() {
    const e = escapeHtml;
    const page = this.draft?.pages.find(p=>p.id === this.pageId);
    let content = "<p>Завантаження…</p>";
    if (this.data) {
      if (this.tab === "panels") {
        content = `<h2>Панелі</h2><p class="muted">Панелі з’являються після підключення через MQTT. Для призначення спочатку застосуйте профіль.</p>`;
        const panels = Object.values(this.data.panels);
        if (!panels.length) content += `<div class="empty">Поки немає підключених панелей.</div>`;
        for (const panel of panels) {
          const options = Object.values(this.data.applied).filter(p=>p.pages.filter(x=>x.visible).every(x=>panel.capabilities?.templates?.[x.template] === 1));
          content += `<section><h3>${e(panel.name)}</h3><p class="muted">${e(panel.id)} · ${e(statusLabel[panel.result] || panel.result)}</p><label>Активний профіль<select data-panel="${e(panel.id)}" ${this.busy ? "disabled" : ""}><option value="">Виберіть профіль</option>${options.map(p=>`<option value="${e(p.id)}" ${panel.profile_id === p.id ? "selected" : ""}>${e(p.name)} · v${p.revision}</option>`).join("")}</select></label></section>`;
        }
      } else if (!this.draft) {
        content = `<h2>Профілі</h2><p class="muted">Спільні сторінки й налаштування для ваших панелей.</p><div class="row"><input id="new-name" placeholder="Назва нового профілю" maxlength="128">${this.button("create","Створити профіль","",true)}</div>`;
        const profiles = Object.values(this.data.profiles);
        if (!profiles.length) content += `<div class="empty">Створіть перший профіль. Він міститиме «Погоду» й «Освітлення».</div>`;
        for (const profile of profiles) content += `<section class="row"><div class="grow"><h3>${e(profile.name)}</h3><p class="muted">${profile.pages.length} сторінок · збережено v${profile.revision} · ${this.data.applied[profile.id] ? "застосовано v"+this.data.applied[profile.id].revision : "ще не застосовано"}</p></div>${this.button("open","Редагувати",`data-id="${e(profile.id)}"`)}</section>`;
      } else {
        content = `<div class="row">${this.button("back",page ? "← До сторінок" : "← До профілів")}<span class="grow"></span><span class="muted">${this.dirty ? "Є незбережені зміни" : "Збережено"}</span>${this.button("save","Зберегти")}${this.button("apply","Застосувати",this.dirty ? "disabled title='Спочатку збережіть зміни'" : "",true)}</div>`;
        if (page) content += this.pageForm(page);
        else {
          content += `<h2>Сторінки профілю</h2><label>Назва профілю<input data-profile-name value="${e(this.draft.name)}" maxlength="128"></label>`;
          this.draft.pages.forEach((p,index)=> {
            content += `<section class="row page" draggable="${!this.busy}" data-index="${index}"><div class="grow"><h3>${e(p.name)}</h3><span class="muted">${p.template === "lighting" ? "Освітлення" : "Погода"}${p.entity_id ? " · "+e(p.entity_id) : " · виберіть сутність"}</span></div><label class="check"><input type="checkbox" data-visible="${e(p.id)}" ${p.visible ? "checked" : ""}>Показувати на панелі</label>${this.button("up","↑",`data-id="${e(p.id)}" ${index===0 ? "disabled" : ""} aria-label="Вгору"`)}${this.button("down","↓",`data-id="${e(p.id)}" ${index===this.draft.pages.length-1 ? "disabled" : ""} aria-label="Вниз"`)}${this.button("edit","Налаштувати",`data-id="${e(p.id)}"`)}${this.button("remove","Видалити",`data-id="${e(p.id)}"`)}</section>`;
          });
          content += `<div class="row"><select id="template"><option value="weather">Погода</option><option value="lighting">Освітлення</option></select>${this.button("add","Додати сторінку")}</div>`;
        }
      }
    }
    this.shadowRoot.innerHTML = `<style>
      :host{display:block;color:var(--primary-text-color,#172635);background:var(--primary-background-color,#f5f7fa);min-height:100vh;font-family:var(--paper-font-body1_-_font-family,system-ui)}
      *{box-sizing:border-box}header{background:var(--card-background-color,#fff);padding:20px 28px;border-bottom:1px solid var(--divider-color,#ddd)}h1{font-size:22px;margin:0 0 16px}h2{font-size:24px}h3{margin:0 0 8px;font-size:17px}main{max-width:1050px;margin:auto;padding:24px}nav,.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.grow{flex:1;min-width:150px}section{background:var(--card-background-color,#fff);border:1px solid var(--divider-color,#ddd);border-radius:14px;padding:20px;margin:16px 0}button,input,select{font:inherit;border:1px solid var(--divider-color,#ccc);border-radius:8px;padding:10px 14px;color:inherit;background:var(--card-background-color,#fff)}button{cursor:pointer}button.primary,nav button.selected{background:var(--primary-color,#087e8b);color:#fff;border-color:transparent}button:disabled{opacity:.5;cursor:default}label{display:block;margin:16px 0}label>input:not([type=checkbox]),label>select{display:block;width:100%;margin-top:8px}input[type=checkbox]{width:18px;height:18px;vertical-align:middle}label.check{margin:4px 0}.muted{color:var(--secondary-text-color,#667788);font-size:14px}.empty{padding:40px;text-align:center;border:1px dashed var(--divider-color,#ccc);border-radius:14px;margin-top:24px}.notice{padding:16px;background:var(--card-background-color,#fff);border-left:4px solid var(--primary-color,#087e8b);white-space:pre-line;border-radius:6px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:0 24px}input:disabled{opacity:.5}@media(max-width:650px){main{padding:16px}.grid{grid-template-columns:1fr}.page{align-items:flex-start}header{padding:16px}}
    </style><header><h1>VIEWE Smart Panel</h1><nav>${this.button("profiles","Профілі","",this.tab==="profiles")}${this.button("panels","Панелі","",this.tab==="panels")}${this.button("refresh","Оновити стан")}</nav></header><main>${this.notice ? `<p class="notice" role="status">${e(this.notice)}</p>` : ""}${content}</main>`;
    if(this.busy) this.shadowRoot.querySelectorAll("input,select").forEach(el=>el.disabled=true);
    this.bind();
  }
  pageForm(page) {
    const e = escapeHtml;
    const entities = this.data.entities.filter(x=>x.entity_id.startsWith(page.template === "lighting" ? "light." : "weather."));
    const entity = entities.find(x=>x.entity_id===page.entity_id);
    let html = `<h2>${page.template === "lighting" ? "Освітлення" : "Погода"}</h2><section><label>Назва сторінки<input data-field="name" value="${e(page.name)}" maxlength="128"></label><label>${page.template === "lighting" ? "Сутність світла" : "Джерело погоди"}<select data-field="entity_id"><option value="">Виберіть сутність</option>${page.entity_id && !entity ? `<option selected value="${e(page.entity_id)}">${e(page.entity_id)} — відсутня</option>` : ""}${entities.map(x=>`<option value="${e(x.entity_id)}" ${x.entity_id===page.entity_id ? "selected" : ""}>${e(x.name)} (${e(x.entity_id)})</option>`).join("")}</select></label>`;
    if (page.template === "lighting") {
      const types = ["AUTO", ...(entity?.types || [])];
      if (!types.includes(page.control_type)) types.push(page.control_type);
      html += `<label>Тип керування<select data-field="control_type">${types.map(type=>`<option value="${type}" ${page.control_type===type ? "selected" : ""} ${type!=="AUTO" && !entity?.types.includes(type) ? "disabled" : ""}>${type === "AUTO" ? "Визначати автоматично" : type}</option>`).join("")}</select></label><p class="muted">Автоматичний тип визначається за можливостями вибраного світла.</p></section>`;
    } else {
      const u = page.umbrella;
      html += `</section><section><h3>Бери парасолю</h3><label class="check"><input type="checkbox" data-umbrella="enabled" ${u.enabled ? "checked" : ""}> Показувати плашку</label><div class="grid"><label>Поріг ймовірності дощу, %<input type="number" min="0" max="100" data-umbrella="probability" value="${u.probability}" ${!u.enabled ? "disabled" : ""}></label><label class="check"><input type="checkbox" data-umbrella="limit_time" ${u.limit_time ? "checked" : ""} ${!u.enabled ? "disabled" : ""}> Обмежувати час показу</label><label>Початок вікна прогнозу<input type="time" data-umbrella="forecast_start" value="${e(u.forecast_start)}" ${!u.enabled ? "disabled" : ""}></label><label>Кінець вікна прогнозу<input type="time" data-umbrella="forecast_end" value="${e(u.forecast_end)}" ${!u.enabled ? "disabled" : ""}></label><label>Приховувати після<input type="time" data-umbrella="hide_after" value="${e(u.hide_after)}" ${!u.enabled || !u.limit_time ? "disabled" : ""}></label></div><p class="muted">Вимкнені параметри зберігаються для повторного ввімкнення.</p></section>`;
    }
    return html;
  }
  bind() {
    const root = this.shadowRoot;
    root.querySelectorAll("button[data-action]").forEach(button=>button.addEventListener("click",()=>this.action(button.dataset.action,button.dataset.id)));
    root.querySelector("[data-profile-name]")?.addEventListener("input",event=> {this.draft.name=event.target.value;this.markDirty();});
    root.querySelectorAll("[data-visible]").forEach(el=>el.addEventListener("change",()=>{this.draft.pages.find(p=>p.id===el.dataset.visible).visible=el.checked;this.dirty=true;this.render();}));
    root.querySelectorAll("[data-field]").forEach(el=>el.addEventListener(el.tagName === "INPUT" ? "input" : "change",()=> {
      const page = this.draft.pages.find(p=>p.id===this.pageId);
      const field = el.dataset.field;
      page[field] = el.value;
      if (field === "name") page.name_auto = false;
      if (field === "entity_id") {
        const entity = this.data.entities.find(x=>x.entity_id===el.value);
        if (page.name_auto && entity) page.name = entity.name;
        if (page.template==="lighting") page.control_type="AUTO";
      }
      this.markDirty();
      if (field !== "name") this.render();
    }));
    root.querySelectorAll("[data-umbrella]").forEach(el=>el.addEventListener("change",()=> {
      const page = this.draft.pages.find(p=>p.id===this.pageId);
      page.umbrella[el.dataset.umbrella] = el.type==="checkbox" ? el.checked : el.type==="number" ? Number(el.value) : el.value;
      this.dirty=true;this.render();
    }));
    root.querySelectorAll("[data-panel]").forEach(el=>el.addEventListener("change",()=>this.perform(async()=> {
      if (!el.value) return;
      const result = await this.api("assign",{panel_id:el.dataset.panel,profile_id:el.value});
      this.data = await this.api("get");
      this.notice = statusLabel[result] || result;
    })));
    root.querySelectorAll("[draggable]").forEach(el=> {
      el.addEventListener("dragstart",event=>event.dataTransfer.setData("text/plain",el.dataset.index));
      el.addEventListener("dragover",event=>event.preventDefault());
      el.addEventListener("drop",event=> {
        event.preventDefault();
        const from=Number(event.dataTransfer.getData("text/plain")),to=Number(el.dataset.index);
        if (!Number.isInteger(from) || from<0 || from>=this.draft.pages.length) return;
        this.draft.pages.splice(to,0,this.draft.pages.splice(from,1)[0]);this.dirty=true;this.render();
      });
    });
  }
  markDirty() {
    this.dirty=true;
    const apply=this.shadowRoot.querySelector('[data-action="apply"]');
    if(apply)apply.disabled=true;
    const indicator=this.shadowRoot.querySelector('[data-action="save"]')?.previousElementSibling;
    if(indicator)indicator.textContent="Є незбережені зміни";
  }
  action(action,id) {
    if (action==="profiles" || action==="panels") {if(!this.leave())return;this.draft=null;this.dirty=false;this.pageId=null;this.tab=action;this.render();return;}
    if (action==="open") {this.draft=structuredClone(this.data.profiles[id]);this.pageId=null;this.dirty=false;this.render();return;}
    if (action==="edit") {this.pageId=id;this.render();return;}
    if (action==="back") {if(this.pageId)this.pageId=null;else {if(!this.leave())return;this.draft=null;this.dirty=false;}this.render();return;}
    if (action==="up" || action==="down") {const i=this.draft.pages.findIndex(p=>p.id===id),j=i+(action==="up"?-1:1);if(j<0||j>=this.draft.pages.length)return;[this.draft.pages[i],this.draft.pages[j]]=[this.draft.pages[j],this.draft.pages[i]];this.dirty=true;this.render();return;}
    if (action==="remove") {if(!window.confirm("Видалити сторінку з профілю?"))return;this.draft.pages=this.draft.pages.filter(p=>p.id!==id);this.dirty=true;this.render();return;}
    // Capture input before perform() redraws the DOM.
    const name=this.shadowRoot.querySelector("#new-name")?.value.trim();
    const template=this.shadowRoot.querySelector("#template")?.value;
    this.perform(async()=> {
      if (action==="create") {if(!name)throw new Error("Введіть назву профілю");this.draft=await this.api("create",{name});this.pageId=null;this.dirty=false;this.data=await this.api("get");}
      if (action==="save") await this.save();
      if (action==="apply") {
        if(this.dirty)throw new Error("Спочатку збережіть зміни");
        const result=await this.api("apply",{profile_id:this.draft.id});
        this.data=await this.api("get");
        const panels=Object.entries(result.panels);
        this.notice=panels.length ? panels.map(([panel,status])=>`${this.data.panels[panel]?.name || panel}: ${statusLabel[status] || status}`).join("\n") : "Версію застосовано в HA. Підключіть панель і призначте їй профіль у розділі «Панелі».";
      }
      if (action==="add") {const page=await this.api("page",{template});this.draft.pages.push(page);this.pageId=page.id;this.dirty=true;}
      if (action==="refresh") {this.data=await this.api("get");this.notice="Стан оновлено";}
    });
  }
}
customElements.define("viewe-panel",ViewePanel);
