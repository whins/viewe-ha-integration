import en from "./locales/en.js";
import uk from "./locales/uk.js";
import {englishError} from "./locales/errors.js";
import {profileEntities,controlAction} from "./profile-controls.js";
import {showToast,closeToast,closeErrorDetails} from "./notifications.js";
const UI_VERSION = "0.2.8";
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));


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
    this.loadError = false;
    this.statusGeneration = 0;
  }
  t(key) { return (this.language === "uk" ? uk : en)[key] || en[key] || key; }
  errorText(error) { const message=error?.message || String(error); return this.language === "uk" ? message : englishError(message,this.t("requestFailed")); }
  notify(message,options={}) {
    showToast(this,message,{detailsLabel:this.t("notificationDetails"),title:this.t("notificationError"),closeLabel:this.t("closeNotification"),...options});
  }
  notifyError(error,options={}) { this.notify(this.errorText(error),{error:true,...options}); }
  clearFeedback() { closeToast(this); }
  notifyResult(result) { this.notify(this.t(result),{error:["error","timeout","incompatible"].includes(result)}); }
  set hass(value) {
    const language = (value.locale?.language || value.language || "en").split("-")[0] === "uk" ? "uk" : "en";
    const changed = this.language !== language;
    const previous=this._hass;
    this.language = language;
    this._hass = value;
    if (!this.data && !this.loading && !this.loadError && this.isConnected) this.load();
    else if (changed && this.isConnected) this.render();
    else if(this.isConnected && this.tab==="panels" && !this.busy && this.shadowRoot.activeElement?.tagName!=="SELECT" && this.controlStatesChanged(previous,value))this.render();
  }
  connectedCallback() {
    this.startStatusRefresh();
    this.render();
    if (this._hass && !this.data) this.load();
  }
  disconnectedCallback() {
    closeErrorDetails(this);
    this.refreshError="";
    this.statusGeneration++;
    if(this.statusTimer)clearInterval(this.statusTimer);
    this.statusTimer=null;
  }
  startStatusRefresh() {
    if(this.statusTimer || !this.isConnected)return;
    this.statusTimer=setInterval(()=>this.refreshStatus(),5000);
  }
  async refreshStatus() {
    if(!this.isConnected || !this._hass || this.loading || this.busy || this.refreshing)return;
    this.refreshing=true;
    const generation=this.statusGeneration;
    try {
      const data=await this.api("get");
      if(!this.isConnected || generation!==this.statusGeneration || this.busy)return;
      this.data=data;
      if(this.refreshError)closeToast(this,"viewe-editor-refresh");
      this.refreshError="";
      if(this.tab==="panels" && this.shadowRoot.activeElement?.tagName!=="SELECT")this.render();
    } catch(error) {
      if(this.isConnected && generation===this.statusGeneration) {
        const message=this.errorText(error);
        if(message!==this.refreshError)this.notify(message,{error:true,id:"viewe-editor-refresh"});
        this.refreshError=message;
      }
    } finally {this.refreshing=false;}
  }
  async api(action, payload={}) {
    return this._hass.callWS({type:"viewe_smart_panel/editor", action, payload:{...payload, language:this.language || "en"}});
  }
  async load() {
    if(this.loading)return;
    this.loading = true;this.loadError=false;
    try { this.data = await this.api("get"); }
    catch (error) { this.loadError=true;this.notifyError(error); }
    finally { this.loading = false; this.render(); }
  }
  async perform(fn) {
    if (this.busy) return;
    this.busy = true;
    this.clearFeedback();
    this.render();
    try { await fn(); }
    catch (error) { this.notifyError(error); }
    finally { this.busy = false; this.render(); }
  }
  async save() {
    this.draft = await this.api("save", {profile:this.draft});
    this.dirty = false;
    this.data = await this.api("get");
    this.notify(this.t("savedNotice"));
  }
  leave() {
    return !this.dirty || window.confirm(this.t("discard"));
  }
  button(action, label, extra="", primary=false) {
    return `<button data-action="${action}" ${extra} class="${primary ? "primary" : ""}" ${this.busy ? "disabled" : ""}>${label}</button>`;
  }
  controlStatesChanged(previous,current) {
    for(const panel of Object.values(this.data?.panels || {})) {
      for(const entry of profileEntities(this.data.applied?.[panel.profile_id])) {
        for(const id of [entry.entity_id,entry.running_entity_id,entry.guard_script])
          if(id && previous?.states?.[id]!==current.states?.[id])return true;
      }
    }
    return false;
  }
  profileControls(panel) {
    const e=escapeHtml,profile=this.data.applied?.[panel.profile_id];
    if(!profile)return "";
    const states=this._hass?.states || {},entries=profileEntities(profile);
    let html=`<div class="profile-controls"><h4>${this.t("profileControls")} · ${e(profile.name)}</h4>`;
    if(panel.result!=="applied")html+=`<p class="muted">${this.t("profileControlsPending")}</p>`;
    if(profile.pages?.some(p=>p.visible && p.demo))html+=`<p class="muted">${this.t("demoControlsHelp")}</p>`;
    if(!entries.length)html+=`<p class="muted">${this.t("noProfileEntities")}</p>`;
    for(const entry of entries) {
      const state=states[entry.kind==="bc250" ? entry.running_entity_id : entry.entity_id];
      const title=entry.kind==="bc250" ? entry.label : states[entry.entity_id]?.attributes?.friendly_name || entry.label || entry.entity_id;
      let value=this.t("offline");
      if(state) {
        if(state.state==="on" || state.state==="off")value=this.t(state.state==="on" ? "onState" : "offState");
        else if(typeof this._hass?.formatEntityState==="function")value=this._hass.formatEntityState(state);
        else value=state.state+(state.attributes?.unit_of_measurement ? " "+state.attributes.unit_of_measurement : "");
      }
      const action=controlAction(entry,states),domain=entry.entity_id?.split(".")[0];
      const actionLabel=entry.kind==="bc250" ? "startControl" : domain==="light" || domain==="switch" ? "toggleControl" : domain==="script" || domain==="automation" ? "runControl" : null;
      const attributes=`data-id="${e(entry.key)}" data-panel-ref="${e(panel.id)}"`;
      if(entry.kind==="bc250" && !states[entry.guard_script])html+=`<p class="muted">${this.t("guardControlHelp")}</p>`;
      html+=`<div class="entity-control"><div class="grow"><strong>${e(title)}</strong><div class="muted">${e(value)}</div></div>${state ? this.button("entity-info",this.t("detailsControl"),attributes) : ""}${actionLabel ? this.button("entity-control",this.t(actionLabel),attributes+(!action ? " disabled" : "")) : ""}</div>`;
    }
    return html+"</div>";
  }
  panelBadge(panel) {
    const online=panel.online===true;
    const label=this.t(online?"online":"offline");
    const mark=online?'<path d="m8 9 2 2 4-4"/>':'<path d="m3 2 14 14"/>';
    return `<span class="connection-badge ${online ? "online" : "offline"}" role="status" aria-label="${label}"><svg viewBox="0 0 20 20" aria-hidden="true"><rect x="3" y="3" width="14" height="11" rx="1.5"/><path d="M10 14v3m-4 0h8"/>${mark}</svg>${label}</span>`;
  }
  render() {
    const e = escapeHtml;
    const page = this.draft?.pages.find(p=>p.id === this.pageId);
    let content = this.loadError ? `<div class="empty"><p>${this.t("loadFailed")}</p>${this.button("retry-load",this.t("retryLoad"))}</div>` : `<p>${this.t("loading")}</p>`;
    if (this.data) {
      if (this.tab === "panels") {
        content = `<h2>${this.t("panels")}</h2><p class="muted">${this.t("panelsHelp")}</p><p class="muted">${this.t("nativeHelp")}</p>`;
        if(this.data.native_setup_required)content+=`<section><h3>${this.t("connectDisplay")}</h3><p>${this.t("connectDisplayHelp")}</p></section>`;
        const panels = Object.values(this.data.panels);
        if (!panels.length) content += `<div class="empty">${this.t("noPanels")}</div>`;
        for (const panel of panels) {
          const options = Object.values(this.data.applied).filter(p=>panel.compatible_profiles?.includes(p.id));
          content += `<section><div class="panel-heading"><h3>${e(panel.name)}</h3>${this.panelBadge(panel)}</div><p class="muted">${e(panel.transport === "esphome" ? "ESPHome Native API" : "MQTT")} · ${e(panel.id)} · ${e(this.t(panel.result))}${panel.error_detail ? " · "+e(panel.error_detail) : ""}</p><label>${this.t("activeProfile")}<select data-panel="${e(panel.id)}" ${this.busy ? "disabled" : ""}><option value="">${this.t("unassigned")}</option>${panel.profile_id && !options.some(p=>p.id===panel.profile_id) ? `<option selected disabled value="${e(panel.profile_id)}">${e(this.data.applied[panel.profile_id]?.name || panel.profile_id)} (${this.t("incompatible")})</option>` : ""}${options.map(p=>`<option value="${e(p.id)}" ${panel.profile_id === p.id ? "selected" : ""}>${e(p.name)} · v${p.revision}</option>`).join("")}</select></label>${panel.transport === "esphome" && panel.profile_id ? this.button("resume-profile",this.t("resumeProfile"),`data-id="${e(panel.id)}"`) : ""} ${this.button("delete-panel",this.t("deletePanel"),`data-id="${e(panel.id)}"`)}${this.profileControls(panel)}</section>`;
          content += `<p class="muted">${this.t("encoder")}: ${this.t(panel.capabilities?.inputs?.encoder === true ? "inputYes" : "inputUnknown")} · ${this.t("touch")}: ${this.t(panel.capabilities?.inputs?.touch === true ? "inputYes" : "inputUnknown")}</p>`;
        }
      } else if (!this.draft) {
        content = `<h2>${this.t("profiles")}</h2><p class="muted">${this.t("profilesHelp")}</p><p class="muted">${this.t("nativeLimits")}</p><div class="row"><input id="new-name" placeholder="${e(this.t("newName"))}" maxlength="128">${this.button("create",this.t("create"),"",true)}</div>`;
        const profiles = Object.values(this.data.profiles);
        if (!profiles.length) content += `<div class="empty">${this.t("noProfiles")}</div>`;
        for (const profile of profiles) content += `<section class="row"><div class="grow"><h3>${e(profile.name)}</h3><p class="muted">${profile.pages.length} ${this.t("pageCount")} · ${this.t("savedVersion")}${profile.revision} · ${this.data.applied[profile.id] ? this.t("appliedVersion")+this.data.applied[profile.id].revision : this.t("notApplied")}</p></div>${this.button("open",this.t("edit"),`data-id="${e(profile.id)}"`)}${this.button("delete-profile",this.t("deleteProfile"),`data-id="${e(profile.id)}"`)}</section>`;
      } else {
        content = `<div class="row">${this.button("back",page ? this.t("backPages") : this.t("backProfiles"))}<span class="grow"></span><span class="muted">${this.dirty ? this.t("unsaved") : this.t("saved")}</span>${this.button("save",this.t("save"))}${this.button("apply",this.t("apply"),this.dirty ? "disabled" : "",true)}</div>`;
        if (page) content += this.pageForm(page);
        else {
          content += `<h2>${this.t("profilePages")}</h2><label>${this.t("profileName")}<input data-profile-name value="${e(this.draft.name)}" maxlength="128"></label>`;
          this.draft.pages.forEach((p,index)=> {
            content += `<section class="row page" draggable="${!this.busy}" data-index="${index}"><div class="grow"><h3>${e(p.name)}</h3><span class="muted">${this.t(p.template)}${p.demo ? " · "+this.t("demo") : ""}${p.entity_id ? " · "+e(p.entity_id) : " · "+this.t("chooseEntityHint")}</span></div><label class="check"><input type="checkbox" data-visible="${e(p.id)}" ${p.visible ? "checked" : ""}>${this.t("showPage")}</label>${this.button("up","↑",`data-id="${e(p.id)}" ${index===0 ? "disabled" : ""} aria-label="${this.t("up")}"`)}${this.button("down","↓",`data-id="${e(p.id)}" ${index===this.draft.pages.length-1 ? "disabled" : ""} aria-label="${this.t("down")}"`)}${this.button("edit",this.t("configure"),`data-id="${e(p.id)}"`)}${this.button("remove",this.t("delete"),`data-id="${e(p.id)}"`)}</section>`;
          });
          content += `<div class="row"><select id="template"><option value="weather">${this.t("weather")}</option><option value="lighting">${this.t("lighting")}</option><option value="switch">${this.t("switch")}</option><option value="bc250">${this.t("bc250")}</option><option value="actions">${this.t("actions")}</option>${["clock","temperature_humidity","thermostat"].map(t=>`<option value="${t}">${this.t(t)}</option>`).join("")}</select>${this.button("add",this.t("addPage"))}</div>`;
        }
      }
    }
    this.shadowRoot.innerHTML = `<style>
      :host{display:block;color:var(--primary-text-color,#172635);background:var(--primary-background-color,#f5f7fa);min-height:100vh;font-family:var(--paper-font-body1_-_font-family,system-ui)}
      *{box-sizing:border-box}header{background:var(--card-background-color,#fff);padding:20px 28px;border-bottom:1px solid var(--divider-color,#ddd)}h1{font-size:22px;margin:0 0 16px}h2{font-size:24px}h3{margin:0 0 8px;font-size:17px}main{max-width:1050px;margin:auto;padding:24px}nav,.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.grow{flex:1;min-width:150px}section{background:var(--card-background-color,#fff);border:1px solid var(--divider-color,#ddd);border-radius:14px;padding:20px;margin:16px 0}button,input,select{font:inherit;border:1px solid var(--divider-color,#ccc);border-radius:8px;padding:10px 14px;color:inherit;background:var(--card-background-color,#fff)}button{cursor:pointer}button.primary,nav button.selected{background:var(--primary-color,#087e8b);color:#fff;border-color:transparent}button:disabled{opacity:.5;cursor:default}label{display:block;margin:16px 0}label>input:not([type=checkbox]),label>select{display:block;width:100%;margin-top:8px}input[type=checkbox]{width:18px;height:18px;vertical-align:middle}label.check{margin:4px 0}.muted{color:var(--secondary-text-color,#667788);font-size:14px}.empty{padding:40px;text-align:center;border:1px dashed var(--divider-color,#ccc);border-radius:14px;margin-top:24px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:0 24px}input:disabled{opacity:.5}@media(max-width:650px){main{padding:16px}.grid{grid-template-columns:1fr}.page{align-items:flex-start}header{padding:16px}}
      .profile-controls{margin-top:18px;border-top:1px solid var(--divider-color,#ddd)}.profile-controls h4{margin-bottom:8px}.entity-control{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:12px 0;border-bottom:1px solid var(--divider-color,#ddd)}
      .panel-heading{display:flex;justify-content:space-between;align-items:center;gap:12px}.panel-heading h3{margin:0;overflow-wrap:anywhere}.connection-badge{display:inline-flex;flex-shrink:0;align-items:center;gap:6px;font-size:12px;font-weight:600;padding:5px 10px;border-radius:20px;white-space:nowrap}.connection-badge.online{color:#38d079;background:#163c29}.connection-badge.offline{color:#ff7869;background:#4a2420}.connection-badge svg{width:15px;height:15px;fill:none;stroke:currentColor;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}
    </style><header><h1>VIEWE Smart Panel <span class="muted">v${UI_VERSION}</span></h1><nav>${this.button("profiles",this.t("profiles"),"",this.tab==="profiles")}${this.button("panels",this.t("panels"),"",this.tab==="panels")}${this.button("refresh",this.t("refresh"))}</nav></header><main>${content}</main>`;
    if(this.busy) this.shadowRoot.querySelectorAll("input,select").forEach(el=>el.disabled=true);
    this.bind();
  }
  pageForm(page) {
    const e=escapeHtml;
    const options=(field,label,values,fallback)=>`<label>${this.t(label)}<select data-field="${field}">${values.map(value=>`<option value="${e(value)}" ${(page[field] ?? fallback)===value ? "selected" : ""}>${e(this.t(value))}</option>`).join("")}</select></label>`;
    let html=`<section><label>${this.t("widgetLabel")}<input data-field="label" value="${e(page.label ?? page.name)}" maxlength="128"></label><p class="muted">${this.t("widgetLabelHelp")}</p><label class="check"><input type="checkbox" data-field="demo" ${page.demo ? "checked" : ""}> ${this.t("demo")}</label><p class="muted">${this.t("demoHelp")}</p><label class="check"><input type="checkbox" data-field="show_label" ${page.show_label!==false ? "checked" : ""}> ${this.t("showLabel")}</label>`;
    const pages={lighting:["cct","color","effects"],weather:["forecast"],thermostat:["modes","fan","presets","swing","range"]}[page.template] || [];
    if(pages.length)html+=`<p>${this.t("disabledPages")}</p>${pages.map(name=>`<label class="check"><input type="checkbox" data-disable-page="${name}" ${(page.disabled_pages || []).includes(name) ? "checked" : ""}> ${this.t(name)}</label>`).join("")}`;
    if(["switch","lighting"].includes(page.template))html+=options("icon","icon",["power","bulb","steam"],page.template==="lighting" ? "bulb" : "power");
    if(page.template==="switch")html+=options("layout","layout",["normal","fullscreen"],"normal");
    if(page.template==="bc250")html+=this.entityField(page,"guard_script","script","guardScript","script.viewe_guarded_start")+`<p class="muted">${this.t("guardHelp")}</p>`;
    let form=this.widgetForm(page);
    if(page.demo)form=form.replace(/(<select data-field="(?:entity_id|power_entity_id|temperature_entity_id|humidity_entity_id)"[^>]*)(>)/g,"$1 disabled$2").replace(/(<select data-run-index="[^"]+"[^>]*)(>)/g,"$1 disabled$2");
    return html+"</section>"+form;
  }
  entityField(page,field,domain,label,fallback="") {
    const e=escapeHtml,value=page[field] ?? fallback;
    const entities=this.data.entities.filter(x=>x.entity_id.startsWith(domain+"."));
    return `<label>${this.t(label)}<select data-field="${field}"><option value="">${this.t("chooseEntity")}</option>${value && !entities.some(x=>x.entity_id===value) ? `<option selected value="${e(value)}">${e(value)} — ${this.t("missing")}</option>` : ""}${entities.map(x=>`<option value="${e(x.entity_id)}" ${x.entity_id===value ? "selected" : ""}>${e(x.name)} (${e(x.entity_id)})</option>`).join("")}</select></label>`;
  }
  widgetForm(page) {
    const e = escapeHtml;
    if (["clock","temperature_humidity","thermostat"].includes(page.template)) {
      const select=(field,label,values,fallback)=>`<label>${this.t(label)}<select data-field="${field}">${values.map(v=>`<option value="${e(v)}" ${(page[field] ?? fallback)===v ? "selected" : ""}>${e(this.t(v))}</option>`).join("")}</select></label>`;
      let html=`<h2>${this.t(page.template)}</h2><section><label>${this.t("pageName")}<input data-field="name" required value="${e(page.name)}" maxlength="128"></label>`;
      if(page.template==="clock")html+=select("theme","clockTheme",["digital","stacked","analog","seconds_ring"],"digital")+select("format","clockFormat",["24h","12h"],"24h");
      if(page.template==="temperature_humidity")html+=this.entityField(page,"temperature_entity_id","sensor","temperatureSensor")+this.entityField(page,"humidity_entity_id","sensor","humiditySensor");
      if(page.template==="thermostat")html+=this.entityField(page,"entity_id","climate","climateEntity")+select("variant","variant",["auto","heater","air_conditioner"],"auto")+select("temperature_unit","temperatureUnit",["auto","°C","°F"],"auto");
      return html+"</section>";
    }
    if (page.template === "bc250") {
      const picker = (field,domain,label) => `<label>${this.t(label)}<select data-field="${field}"><option value="">${this.t("chooseEntity")}</option>${page[field] && !this.data.entities.some(x=>x.entity_id===page[field]) ? `<option selected value="${e(page[field])}">${e(page[field])} — ${this.t("missing")}</option>` : ""}${this.data.entities.filter(x=>x.entity_id.startsWith(domain+".")).map(x=>`<option value="${e(x.entity_id)}" ${x.entity_id===page[field] ? "selected" : ""}>${e(x.name)} (${e(x.entity_id)})</option>`).join("")}</select></label>`;
      return `<h2>BC-250</h2><section><label>${this.t("pageName")}<input data-field="name" required value="${e(page.name)}" maxlength="128"></label>${picker("power_entity_id","button","bc250Power")}${picker("entity_id","binary_sensor","bc250Running")}<p class="muted">${this.t("bc250Help")}</p></section>`;
    }
    if (page.template === "actions") {
      const targets = this.data.entities.filter(x=>/^(script|automation)\./.test(x.entity_id));
      return `<h2>${this.t("actions")}</h2><section><label>${this.t("pageName")}<input data-field="name" required value="${e(page.name)}" maxlength="128"></label><label>${this.t("actionCount")}<select data-action-count><option value="1" ${page.actions.length===1 ? "selected" : ""}>1</option><option value="2" ${page.actions.length===2 ? "selected" : ""}>2</option></select></label>${page.actions.map((a,i)=>`<label>${this.t("actionTarget")} ${i+1}<select data-run-index="${i}" data-run-field="entity_id"><option value="">${this.t("chooseEntity")}</option>${a.entity_id && !targets.some(x=>x.entity_id===a.entity_id) ? `<option selected value="${e(a.entity_id)}">${e(a.entity_id)} — ${this.t("missing")}</option>` : ""}${targets.map(x=>`<option value="${e(x.entity_id)}" ${x.entity_id===a.entity_id ? "selected" : ""}>${e(x.name)} (${e(x.entity_id)})</option>`).join("")}</select></label><label>${this.t("actionName")}<input data-run-index="${i}" data-run-field="name" value="${e(a.name)}" maxlength="128"></label>`).join("")}</section>`;
    }
    const entities = this.data.entities.filter(x=>x.entity_id.startsWith(page.template === "lighting" ? "light." : page.template === "switch" ? "switch." : "weather."));
    const entity = entities.find(x=>x.entity_id===page.entity_id);
    let html = `<h2>${this.t(page.template)}</h2><section><label>${this.t("pageName")}<input data-field="name" required value="${e(page.name)}" maxlength="128"></label><label>${page.template === "lighting" ? this.t("lightEntity") : page.template === "switch" ? this.t("switchEntity") : this.t("weatherEntity")}<select data-field="entity_id"><option value="">${this.t("chooseEntity")}</option>${page.entity_id && !entity ? `<option selected value="${e(page.entity_id)}">${e(page.entity_id)} — ${this.t("missing")}</option>` : ""}${entities.map(x=>`<option value="${e(x.entity_id)}" ${x.entity_id===page.entity_id ? "selected" : ""}>${e(x.name)} (${e(x.entity_id)})</option>`).join("")}</select></label>`;
    if (page.template === "lighting") {
      const types = ["AUTO", ...(entity?.types || [])];
      if (!types.includes(page.control_type)) types.push(page.control_type);
      html += `<label>${this.t("controlType")}<select data-field="control_type">${types.map(type=>`<option value="${type}" ${page.control_type===type ? "selected" : ""} ${type!=="AUTO" && !entity?.types.includes(type) ? "disabled" : ""}>${type === "AUTO" ? this.t("auto") : type}</option>`).join("")}</select></label><p class="muted">${this.t("autoHelp")}</p></section>`;
    } else if (page.template === "weather") {
      const u = page.umbrella;
      html += `</section><section><h3>${this.t("umbrella")}</h3><label class="check"><input type="checkbox" data-umbrella="enabled" ${u.enabled ? "checked" : ""}> ${this.t("showBanner")}</label><div class="grid"><label>${this.t("rainThreshold")}<input type="number" min="0" max="100" data-umbrella="probability" value="${u.probability}" ${!u.enabled ? "disabled" : ""}></label><label class="check"><input type="checkbox" data-umbrella="limit_time" ${u.limit_time ? "checked" : ""} ${!u.enabled ? "disabled" : ""}> ${this.t("limitTime")}</label><label>${this.t("forecastStart")}<input type="time" data-umbrella="forecast_start" value="${e(u.forecast_start)}" ${!u.enabled ? "disabled" : ""}></label><label>${this.t("forecastEnd")}<input type="time" data-umbrella="forecast_end" value="${e(u.forecast_end)}" ${!u.enabled ? "disabled" : ""}></label><label>${this.t("hideAfter")}<input type="time" data-umbrella="hide_after" value="${e(u.hide_after)}" ${!u.enabled || !u.limit_time ? "disabled" : ""}></label></div><p class="muted">${this.t("retainedSettings")}</p></section>`;
    }
    if (page.template === "switch") html += `</section>`;
    return html;
  }
  bind() {
    const root = this.shadowRoot;
    root.querySelector("[data-action-count]")?.addEventListener("change",event=> {
      const page = this.draft.pages.find(p=>p.id===this.pageId);
      if (event.target.value === "2") page.actions.push({entity_id:"",name:""});
      else page.actions = page.actions.slice(0,1);
      this.markDirty(); this.render();
    });
    root.querySelectorAll("[data-run-index]").forEach(el=>el.addEventListener(el.tagName === "INPUT" ? "input" : "change",()=> {
      const page = this.draft.pages.find(p=>p.id===this.pageId);
      page.actions[Number(el.dataset.runIndex)][el.dataset.runField] = el.value;
      this.markDirty();
    }));
    root.querySelectorAll("button[data-action]").forEach(button=>button.addEventListener("click",()=>this.action(button.dataset.action,button.dataset.id,button.dataset.panelRef)));
    root.querySelector("[data-profile-name]")?.addEventListener("input",event=> {this.draft.name=event.target.value;this.markDirty();});
    root.querySelectorAll("[data-visible]").forEach(el=>el.addEventListener("change",()=>{this.draft.pages.find(p=>p.id===el.dataset.visible).visible=el.checked;this.dirty=true;this.render();}));
    root.querySelectorAll("[data-field]").forEach(el=>el.addEventListener(el.tagName === "INPUT" ? "input" : "change",()=> {
      const page = this.draft.pages.find(p=>p.id===this.pageId);
      const field = el.dataset.field;
      page[field] = el.type==="checkbox" ? el.checked : el.value;
      if (field === "name") page.name_auto = false;
      if (field === "entity_id") {
        const entity = this.data.entities.find(x=>x.entity_id===el.value);
        if (page.name_auto && entity) page.name = entity.name;
        if (page.template==="lighting") page.control_type="AUTO";
      }
      this.markDirty();
      if (field !== "name" && field !== "label") this.render();
    }));
    root.querySelectorAll("[data-disable-page]").forEach(el=>el.addEventListener("change",()=> {
      const page=this.draft.pages.find(p=>p.id===this.pageId),name=el.dataset.disablePage;
      const values=new Set(page.disabled_pages || []);
      if(el.checked)values.add(name);else values.delete(name);
      page.disabled_pages=[...values];this.markDirty();
    }));
    root.querySelectorAll("[data-umbrella]").forEach(el=>el.addEventListener("change",()=> {
      const page = this.draft.pages.find(p=>p.id===this.pageId);
      page.umbrella[el.dataset.umbrella] = el.type==="checkbox" ? el.checked : el.type==="number" ? Number(el.value) : el.value;
      this.dirty=true;this.render();
    }));
    root.querySelectorAll("[data-panel]").forEach(el=>el.addEventListener("change",()=>this.perform(async()=> {
      const result = await this.api("assign",{panel_id:el.dataset.panel,profile_id:el.value || null});
      this.data = await this.api("get");
      this.notifyResult(result);
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
    if(indicator)indicator.textContent=this.t("unsaved");
  }
  action(action,id,panelId) {
    if(action==="retry-load")return this.load();
    if(action==="entity-info" || action==="entity-control") {
      const panel=this.data.panels[panelId];
      const entry=profileEntities(this.data.applied?.[panel?.profile_id]).find(item=>item.key===id);
      if(!entry)return;
      if(action==="entity-info") {
        this.dispatchEvent(new CustomEvent("hass-more-info",{detail:{entityId:entry.info_entity_id},bubbles:true,composed:true}));
        return;
      }
      return this.perform(async()=> {
        const operation=controlAction(entry,this._hass.states || {});
        if(!operation)throw new Error(this.t("controlUnavailable"));
        await this._hass.callService(operation.domain,operation.service,operation.data);
        this.notify(this.t("controlSent"));
      });
    }
    if(action==="delete-panel") {
      if(!window.confirm(this.t("deletePanelConfirm")))return;
      return this.perform(async()=> {
        await this.api("delete_panel",{panel_id:id});
        this.data=await this.api("get");this.notify(this.t("panelDeleted"));
      });
    }
    if(action==="resume-profile")return this.perform(async()=> {
      const result=await this.api("assign",{panel_id:id,profile_id:this.data.panels[id].profile_id});
      this.data=await this.api("get");this.notifyResult(result);
    });
    if(action==="delete-profile") {
      if(!window.confirm(this.t("deleteProfileConfirm")))return;
      return this.perform(async()=> {
        if(Object.values(this.data.panels).some(p=>p.profile_id===id))throw new Error(this.t("deleteAssigned"));
        await this.api("delete",{profile_id:id,revision:this.data.profiles[id].revision});
        this.data=await this.api("get");this.notify(this.t("deleted"));
      });
    }
    if (action==="profiles" || action==="panels") {if(!this.leave())return;this.draft=null;this.dirty=false;this.pageId=null;this.tab=action;this.render();return;}
    if (action==="open") {this.draft=structuredClone(this.data.profiles[id]);this.pageId=null;this.dirty=false;this.render();return;}
    if (action==="edit") {this.pageId=id;this.render();return;}
    if (action==="back") {if(this.pageId)this.pageId=null;else {if(!this.leave())return;this.draft=null;this.dirty=false;}this.render();return;}
    if (action==="up" || action==="down") {const i=this.draft.pages.findIndex(p=>p.id===id),j=i+(action==="up"?-1:1);if(j<0||j>=this.draft.pages.length)return;[this.draft.pages[i],this.draft.pages[j]]=[this.draft.pages[j],this.draft.pages[i]];this.dirty=true;this.render();return;}
    if (action==="remove") {if(!window.confirm(this.t("deletePageConfirm")))return;this.draft.pages=this.draft.pages.filter(p=>p.id!==id);this.dirty=true;this.render();return;}
    // Capture input before perform() redraws the DOM.
    const name=this.shadowRoot.querySelector("#new-name")?.value.trim();
    const template=this.shadowRoot.querySelector("#template")?.value;
    return this.perform(async()=> {
      if (action==="create") {if(!name)throw new Error(this.t("enterName"));this.draft=await this.api("create",{name});this.pageId=null;this.dirty=false;this.data=await this.api("get");}
      if (action==="save") await this.save();
      if (action==="apply") {
        if(this.dirty)throw new Error(this.t("saveFirst"));
        const result=await this.api("apply",{profile_id:this.draft.id});
        this.data=await this.api("get");
        const panels=Object.entries(result.panels);
        this.notify(panels.length ? panels.map(([panel,status])=>`${this.data.panels[panel]?.name || panel}: ${this.t(status)}`).join("\n") : this.t("applyNoPanels"),{error:panels.some(([,status])=>["error","timeout","incompatible"].includes(status))});
      }
      if (action==="add") {const page=await this.api("page",{template});this.draft.pages.push(page);this.pageId=page.id;this.dirty=true;}
      if (action==="refresh") {this.data=await this.api("refresh");this.notify(this.t("refreshed"));}
    });
  }
}
const elementName="viewe-panel-"+UI_VERSION.replaceAll(".","-");
if(!customElements.get?.(elementName))customElements.define(elementName,ViewePanel);
