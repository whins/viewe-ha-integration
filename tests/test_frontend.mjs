import test from "node:test";
import {profileEntities,controlAction} from "../custom_components/viewe_smart_panel/frontend/profile-controls.js";
import {readFileSync} from "node:fs";
const packageVersion=JSON.parse(readFileSync(new URL("../custom_components/viewe_smart_panel/manifest.json",import.meta.url),"utf8")).version;
import assert from "node:assert/strict";
import en from "../custom_components/viewe_smart_panel/frontend/locales/en.js";
import uk from "../custom_components/viewe_smart_panel/frontend/locales/uk.js";
import {englishError} from "../custom_components/viewe_smart_panel/frontend/locales/errors.js";

let Panel,registeredName;
globalThis.HTMLElement=class {
  attachShadow() { this.shadowRoot={innerHTML:"",querySelector:()=>null,querySelectorAll:()=>[]}; }
};
globalThis.customElements={define:(name,component)=>{registeredName=name;Panel=component;}};
globalThis.window={confirm:()=>true};
await import("../custom_components/viewe_smart_panel/frontend/panel.js");

test("BC-250 selects a power button and running sensor independently",()=> {
  const panel=new Panel();panel.language="en";
  panel.data={entities:[{entity_id:"button.power",name:"Power"},{entity_id:"binary_sensor.running",name:"Running"},{entity_id:"switch.psu",name:"PSU"}]};
  const html=panel.pageForm({template:"bc250",name:"BC-250",entity_id:"binary_sensor.running",power_entity_id:"button.power"});
  assert.match(html,/data-field="power_entity_id"/);
  assert.match(html,/selected>Power/);
  assert.match(html,/selected>Running/);
  assert.doesNotMatch(html,/switch.psu/);
  assert.match(html,/10 seconds/);
});

test("English and Ukrainian interface keys stay in sync",()=> {
  assert.deepEqual(Object.keys(en).sort(),Object.keys(uk).sort());
  for(const value of Object.values(en))assert.doesNotMatch(value,/[\u0400-\u04ff]/);
});

test("English renders labels and deletion without panel requirements",()=> {
  const panel=new Panel();panel.language="en";
  panel.data={profiles:{p:{id:"p",name:"Home",revision:1,pages:[]}},applied:{},panels:{},entities:[]};
  panel.render();
  assert.match(panel.shadowRoot.innerHTML,/placeholder="New profile name"/);
  assert.match(panel.shadowRoot.innerHTML,/Delete profile/);
  panel.draft=structuredClone(panel.data.profiles.p);panel.render();
  assert.doesNotMatch(panel.shadowRoot.innerHTML,/Encoder required|Panel requirements|data-requirement/);
  assert.doesNotMatch(panel.shadowRoot.innerHTML,/Touch required/);
  assert.doesNotMatch(panel.shadowRoot.innerHTML,/\$\{this\.t|=this\.t/);
});

test("HA language selects Ukrainian or English fallback",()=> {
  const panel=new Panel();
  panel.hass={locale:{language:"uk"}};
  assert.equal(panel.t("profiles"),"Профілі");
  panel.hass={locale:{language:"de"}};
  assert.equal(panel.t("profiles"),"Profiles");
});

test("Panel selector uses server compatibility results",()=> {
  const panel=new Panel();panel.language="en";panel.tab="panels";
  panel.data={profiles:{},applied:{ok:{id:"ok",name:"Compatible",revision:1},no:{id:"no",name:"Incompatible profile",revision:1}},panels:{a:{id:"a",name:"Panel",compatible_profiles:["ok"],capabilities:{inputs:{encoder:true,touch:false}}}},entities:[]};
  panel.render();
  assert.match(panel.shadowRoot.innerHTML,/value="ok"/);
  assert.doesNotMatch(panel.shadowRoot.innerHTML,/value="no"/);
  assert.match(panel.shadowRoot.innerHTML,/>No profile<\/option>/);
  panel.data.panels.a.profile_id="no";
  panel.render();
  assert.match(panel.shadowRoot.innerHTML,/selected disabled value="no"/);
});

test("Deletion sends displayed revision and refreshes profiles",async()=> {
  const panel=new Panel();panel.language="en";
  panel.data={profiles:{p:{id:"p",name:"Home",revision:3,pages:[]}},panels:{},applied:{},entities:[]};
  const calls=[];
  panel.api=async(action,payload)=>{calls.push([action,payload]);return {profiles:{},panels:{},applied:{},entities:[]};};
  await panel.action("delete-profile","p");
  assert.deepEqual(calls[0],["delete",{profile_id:"p",revision:3}]);
  assert.equal(panel.notice,"Profile deleted");
});

test("Server validation errors remain useful in English",()=> {
  assert.equal(englishError("Профіль не знайдено","Error"),"Profile not found");
  assert.equal(englishError("Профіль несумісний із панелями: Kitchen","Error"),"Profile incompatible with panels: Kitchen");
});

test("English detail forms render both templates without unresolved labels",()=> {
  const panel=new Panel();panel.language="en";
  panel.data={entities:[]};
  const lighting=panel.pageForm({template:"lighting",name:"Room",entity_id:"",control_type:"AUTO"});
  const weather=panel.pageForm({template:"weather",name:"Weather",entity_id:"",umbrella:{enabled:true,probability:40,forecast_start:"08:00",forecast_end:"18:00",limit_time:true,hide_after:"10:00"}});
  assert.match(lighting,/Detect automatically/);
  assert.match(weather,/Rain probability threshold/);
  assert.doesNotMatch(lighting+weather,/\$\{this\.t|=this\.t|[\u0400-\u04ff]/);
});

test("CCT appears as an available selected control type for temperature lights",()=> {
  const panel=new Panel();panel.language="en";
  panel.data={entities:[{entity_id:"light.white",name:"White",types:["MONO","CCT"]}]};
  const html=panel.pageForm({template:"lighting",name:"White",entity_id:"light.white",control_type:"CCT"});
  assert.match(html,/<option value="CCT" selected >CCT<\/option>/);
});

test("Switch form selects only switches and omits light/weather settings",()=> {
  const panel=new Panel();panel.language="en";
  panel.data={entities:[{entity_id:"switch.socket",name:"Socket",types:[]},{entity_id:"light.kitchen",name:"Kitchen",types:[]}]};
  const html=panel.pageForm({id:"s",template:"switch",name:"Socket",entity_id:"switch.socket"});
  assert.match(html,/Switch entity/);assert.match(html,/switch.socket/);
  assert.doesNotMatch(html,/light.kitchen|data-umbrella|control_type/);
});


test("Actions form supports two targets, filters domains and escapes labels",()=> {
  const panel=new Panel();panel.language="en";
  panel.data={entities:[{entity_id:"script.scene",name:"Scene"},{entity_id:"automation.scene",name:"Automation"},{entity_id:"light.room",name:"Room"}]};
  const html=panel.pageForm({template:"actions",name:"Actions",actions:[{entity_id:"script.scene",name:"<Start>"},{entity_id:"automation.scene",name:""}]});
  assert.match(html,/script.scene/);assert.match(html,/automation.scene/);
  assert.match(html,/value="2" selected/);assert.match(html,/&lt;Start&gt;/);
  assert.match(html,/data-run-index="1"/);assert.doesNotMatch(html,/light.room/);
});


test("New widget forms expose only relevant entities and preserve hidden labels",()=> {
  const panel=new Panel();panel.language="en";
  panel.data={entities:[{entity_id:"sensor.temp",name:"Temperature"},{entity_id:"climate.room",name:"Climate"},{entity_id:"switch.room",name:"Switch"}]};
  const clock=panel.pageForm({template:"clock",name:"Clock",format:"12h",show_label:false});
  assert.match(clock,/value="12h" selected/);
  assert.doesNotMatch(clock,/data-field="show_label" checked|data-field="entity_id"|climate.room/);
  const room=panel.pageForm({template:"temperature_humidity",name:"Room",temperature_entity_id:"sensor.temp"});
  assert.match(room,/sensor.temp/);assert.match(room,/humidity_entity_id/);
  assert.doesNotMatch(room,/climate.room|switch.room/);
  const climate=panel.pageForm({template:"thermostat",name:"Climate",entity_id:"climate.room",variant:"heater",temperature_unit:"°F",disabled_pages:["swing"]});
  assert.match(climate,/climate.room/);assert.match(climate,/value="heater" selected/);
  assert.match(climate,/value="°F" selected/);assert.match(climate,/data-disable-page="swing" checked/);
  assert.doesNotMatch(climate,/sensor.temp|switch.room/);
});

test("Label checkbox and internal page handlers save actual booleans and page names",()=> {
  const panel=new Panel();panel.language="en";
  panel.draft={pages:[{id:"one",show_label:true,disabled_pages:[]}]};panel.pageId="one";
  const callbacks={};
  const label={tagName:"INPUT",type:"checkbox",checked:false,dataset:{field:"show_label"},addEventListener:(event,fn)=>callbacks.label=fn};
  const page={checked:true,dataset:{disablePage:"color"},addEventListener:(event,fn)=>callbacks.page=fn};
  panel.render=()=>{};
  panel.shadowRoot.querySelectorAll=selector=>selector==='[data-field]' ? [label] : selector==='[data-disable-page]' ? [page] : [];
  panel.bind();callbacks.label();callbacks.page();
  assert.equal(panel.draft.pages[0].show_label,false);
  assert.deepEqual(panel.draft.pages[0].disabled_pages,["color"]);
  page.checked=false;callbacks.page();assert.deepEqual(panel.draft.pages[0].disabled_pages,[]);
});

test("ESPHome panels expose local override status and explicit resume",()=> {
  const panel=new Panel();panel.language="en";panel.tab="panels";
  panel.data={profiles:{},applied:{p:{id:"p",name:"Home",revision:1}},panels:{one:{id:"one",name:"Panel",transport:"esphome",profile_id:"p",compatible_profiles:["p"],result:"local_override",error_detail:"<unsafe>"}},entities:[]};
  panel.render();const html=panel.shadowRoot.innerHTML;
  assert.match(html,/ESPHome Native API/);assert.match(html,/YAML profile selected/);
  assert.match(html,/data-action="resume-profile"/);assert.match(html,/&lt;unsafe&gt;/);
});


test("Demo checkbox appears for all widgets and preserves entity selection",()=> {
 const panel=new Panel();panel.language="uk";panel.data={entities:[]};
 for(const template of ["switch","lighting","weather","bc250","clock","temperature_humidity","thermostat","actions"]) {
  const page={id:"one",template,name:"Demo",demo:true,entity_id:"switch.room",control_type:"AUTO",actions:[{entity_id:"script.scene",name:"Scene"}],umbrella:{enabled:true,probability:40,limit_time:true,forecast_start:"08:00",forecast_end:"18:00",hide_after:"10:00"}};
  const html=panel.pageForm(page);
  assert.match(html,/data-field="demo" checked/);assert.match(html,/Демо/);
  if(["switch","lighting","weather","thermostat"].includes(template))assert.match(html,/<select data-field="entity_id" disabled>/);
  assert.equal(page.entity_id,"switch.room");
 }
});

test("Demo checkbox handler persists a boolean and can be disabled",()=> {
 const panel=new Panel();panel.draft={pages:[{id:"one",demo:false}]};panel.pageId="one";panel.render=()=>{};
 let handler;
 const checkbox={tagName:"INPUT",type:"checkbox",checked:true,dataset:{field:"demo"},addEventListener:(_,fn)=>handler=fn};
 panel.shadowRoot.querySelectorAll=selector=>selector==='[data-field]'?[checkbox]:[];
 panel.bind();handler();assert.equal(panel.draft.pages[0].demo,true);
 checkbox.checked=false;handler();assert.equal(panel.draft.pages[0].demo,false);
});


test("Versioned component renders the installed editor version",()=> {
 const panel=new Panel();panel.language="en";panel.render();
 assert.ok(panel.shadowRoot.innerHTML.includes(`v${packageVersion}`));
 assert.equal(registeredName,"viewe-panel-"+packageVersion.replaceAll(".","-"));
});

test("Panels refresh displays new ESPHome data without manual interaction",async()=> {
 const panel=new Panel();panel.language="en";panel.isConnected=true;panel._hass={};panel.tab="panels";
 panel.data={panels:{legacy:{id:"legacy",name:"Old panel",result:"offline"}},profiles:{},applied:{},entities:[]};
 const next={...panel.data,panels:{...panel.data.panels,new:{id:"new",name:"New ESPHome display",transport:"esphome",result:"applied"}}};
 panel.api=async()=>next;
 await panel.refreshStatus();
 assert.match(panel.shadowRoot.innerHTML,/New ESPHome display/);
 assert.match(panel.shadowRoot.innerHTML,/ESPHome Native API/);
 assert.match(panel.shadowRoot.innerHTML,/Old panel/);
});

test("Background refresh preserves unsaved widget edits and does not redraw form",async()=> {
 const panel=new Panel();panel.isConnected=true;panel._hass={};panel.tab="profiles";
 const draft={id:"p",pages:[{id:"w",demo:true,name:"Unsaved name"}]};
 panel.draft=draft;panel.pageId="w";panel.dirty=true;panel.data={old:true};
 let renders=0;panel.render=()=>renders++;panel.api=async()=>({profiles:{},panels:{}});
 await panel.refreshStatus();
 assert.equal(panel.draft,draft);assert.equal(panel.dirty,true);assert.equal(panel.pageId,"w");assert.equal(renders,0);
});

test("Polling stops on disconnect and late responses cannot overwrite current data",async()=> {
 const previousSet=globalThis.setInterval,previousClear=globalThis.clearInterval;
 let callback,cleared,period;
 try {
  globalThis.setInterval=(fn,ms)=>{callback=fn;period=ms;return 42;};
  globalThis.clearInterval=id=>cleared=id;
  const panel=new Panel();panel.isConnected=true;panel._hass={};panel.data={current:true};
  panel.startStatusRefresh();assert.equal(period,5000);assert.equal(typeof callback,"function");
  let resolve;panel.api=()=>new Promise(done=>resolve=done);
  const pending=panel.refreshStatus();panel.disconnectedCallback();panel.isConnected=false;
  resolve({stale:true});await pending;
  assert.equal(cleared,42);assert.deepEqual(panel.data,{current:true});assert.equal(panel.refreshing,false);
 } finally {globalThis.setInterval=previousSet;globalThis.clearInterval=previousClear;}
});

test("Refresh does not overwrite the result of an ongoing save or assignment",async()=> {
 const panel=new Panel();panel.isConnected=true;panel._hass={};panel.data={current:true};
 let calls=0,resolve;panel.api=()=>{calls++;return new Promise(done=>resolve=done);};
 panel.busy=true;await panel.refreshStatus();assert.equal(calls,0);
 panel.busy=false;const pending=panel.refreshStatus();panel.busy=true;
 resolve({stale:true});await pending;assert.deepEqual(panel.data,{current:true});
});

test("ESPHome setup guidance remains visible alongside stored MQTT panels",()=> {
 const panel=new Panel();panel.language="uk";panel.tab="panels";
 panel.data={native_setup_required:true,profiles:{},applied:{},entities:[],panels:{old:{id:"old",name:"Old panel",result:"offline"}}};
 panel.render();const html=panel.shadowRoot.innerHTML;
 assert.match(html,/ESPHome/);assert.match(html,/6053/);assert.match(html,/Old panel/);assert.match(html,/Додати інтеграцію/);
});


test("Panel polling does not interrupt an open profile selector",async()=> {
 const panel=new Panel();panel.isConnected=true;panel._hass={};panel.tab="panels";
 panel.shadowRoot.activeElement={tagName:"SELECT"};let renders=0;
 panel.render=()=>renders++;panel.api=async()=>({panels:{new:{name:"New panel"}}});
 await panel.refreshStatus();assert.equal(renders,0);assert.equal(panel.data.panels.new.name,"New panel");
 panel.shadowRoot.activeElement=null;await panel.refreshStatus();assert.equal(renders,1);
});


test("Online badges follow connection state independently of delivery result",()=> {
 const panel=new Panel();panel.language="en";
 assert.match(panel.panelBadge({online:true,result:"error"}),/connection-badge online/);
 assert.match(panel.panelBadge({online:true}),/>Online</);
 assert.match(panel.panelBadge({online:false,result:"applied"}),/connection-badge offline/);
 assert.match(panel.panelBadge({online:false}),/>Offline</);
});

test("Panel cards include removal with explicit confirmation",async()=> {
 const panel=new Panel();panel.language="en";panel.tab="panels";
 panel.data={panels:{one:{id:"one",name:"Room",online:true,result:"applied"}},profiles:{},applied:{},entities:[]};
 panel.render();assert.match(panel.shadowRoot.innerHTML,/data-action="delete-panel"/);
 const calls=[];panel.api=async(action,payload)=>{calls.push([action,payload]);return action==="get" ? {panels:{},profiles:{},applied:{},entities:[]} : {deleted:"one"};};
 await panel.action("delete-panel","one");
 assert.deepEqual(calls[0],["delete_panel",{panel_id:"one"}]);assert.equal(calls[1][0],"get");
});

test("Cancelling removal keeps the panel and explicit Refresh requests rediscovery",async()=> {
 const panel=new Panel();panel.language="en";panel.data={panels:{},profiles:{},applied:{},entities:[]};
 let calls=[];panel.api=async(action)=>{calls.push(action);return panel.data;};
 const confirm=window.confirm;
 try {window.confirm=()=>false;await panel.action("delete-panel","one");assert.deepEqual(calls,[]);} finally {window.confirm=confirm;}
 await panel.action("refresh");assert.deepEqual(calls,["refresh"]);
});


function profileControlPanel(pages) {
 const panel=new Panel();panel.language="en";panel.tab="panels";
 panel.data={panels:{one:{id:"one",name:"Panel",profile_id:"p",result:"applied"}},profiles:{},applied:{p:{id:"p",name:"Home",pages}},entities:[]};
 panel._hass={states:{}};return panel;
}

test("Profile control collection deduplicates real entities and excludes demos, hidden widgets and clocks",()=> {
 const entries=profileEntities({pages:[
  {id:"a",visible:true,template:"lighting",entity_id:"light.room"},
  {id:"b",visible:true,template:"lighting",entity_id:"light.room"},
  {id:"c",visible:true,template:"switch",demo:true,entity_id:"switch.demo"},
  {id:"d",visible:false,template:"thermostat",entity_id:"climate.hidden"},
  {id:"e",visible:true,template:"clock"},
  {id:"f",visible:true,template:"temperature_humidity",temperature_entity_id:"sensor.temp",humidity_entity_id:"sensor.humidity"},
  {id:"g",visible:true,template:"actions",actions:[{entity_id:"script.scene"},{entity_id:"automation.evening"}]}
 ]});
 assert.deepEqual(entries.map(e=>e.entity_id),["light.room","sensor.temp","sensor.humidity","script.scene","automation.evening"]);
});

test("BC-250 controls always use the guard script and never raw Power press",()=> {
 const entry=profileEntities({pages:[{id:"bc",visible:true,template:"bc250",name:"PC",entity_id:"binary_sensor.running",power_entity_id:"button.power",guard_script:"script.guarded"}]})[0];
 const states={"binary_sensor.running":{state:"off"},"button.power":{state:"unknown"},"script.guarded":{state:"off"}};
 const operation=controlAction(entry,states);
 assert.equal(operation.domain,"script");assert.equal(operation.service,"turn_on");
 assert.deepEqual(operation.data,{entity_id:"script.guarded",variables:{state_entity_id:"binary_sensor.running",control_entity_id:"button.power"}});
 assert.equal(entry.info_entity_id,"binary_sensor.running");
 for(const bad of ["on","unknown","unavailable"]) {
  assert.equal(controlAction(entry,{...states,"binary_sensor.running":{state:bad}}),null);
 }
 const missing={...states};delete missing["script.guarded"];assert.equal(controlAction(entry,missing),null);
 assert.equal(controlAction(entry,{...states,"button.power":{state:"unavailable"}}),null);
});

test("Original HA controls map toggles and runs correctly and block unavailable targets",()=> {
 for(const [id,service] of [["light.room","toggle"],["switch.room","toggle"],["script.scene","turn_on"],["automation.evening","trigger"]]) {
  const entry={entity_id:id,kind:"entity"};
  const operation=controlAction(entry,{[id]:{state:"off"}});
  assert.equal(operation.service,service);assert.equal(operation.data.entity_id,id);
  if(id.startsWith("automation."))assert.equal(operation.data.skip_condition,false);
  assert.equal(controlAction(entry,{[id]:{state:"unavailable"}}),null);
  assert.equal(controlAction(entry,{}),null);
 }
 assert.equal(controlAction({entity_id:"climate.room",kind:"entity"},{"climate.room":{state:"heat"}}),null);
});

test("Panel controls use the applied snapshot rather than an unsaved draft",()=> {
 const panel=profileControlPanel([{id:"a",template:"lighting",visible:true,name:"Room",entity_id:"light.applied"}]);
 panel.draft={pages:[{id:"b",template:"lighting",visible:true,entity_id:"light.draft"}]};
 panel._hass.states={"light.applied":{state:"on",attributes:{friendly_name:"<Room>"}}};
 const html=panel.profileControls(panel.data.panels.one);
 assert.match(html,/&lt;Room&gt;/);assert.match(html,/data-id="light.applied"/);assert.doesNotMatch(html,/light.draft/);
});

test("Entity controls call the original HA service without profile mutations",async()=> {
 const panel=profileControlPanel([{id:"a",template:"switch",visible:true,name:"Socket",entity_id:"switch.socket"}]);
 panel._hass.states={"switch.socket":{state:"off",attributes:{}}};
 const calls=[];panel._hass.callService=async(...args)=>calls.push(args);
 await panel.action("entity-control","switch.socket","one");
 assert.deepEqual(calls,[["switch","toggle",{entity_id:"switch.socket"}]]);
 assert.equal(panel.data.applied.p.pages[0].entity_id,"switch.socket");
 await panel.action("entity-control","switch.not_in_profile","one");assert.equal(calls.length,1);
});

test("More-info opens the original climate entity through HA's native dialog",()=> {
 const panel=profileControlPanel([{id:"a",template:"thermostat",visible:true,name:"Room",entity_id:"climate.room"}]);
 let event;panel.dispatchEvent=value=>event=value;
 panel.action("entity-info","climate.room","one");
 assert.equal(event.type,"hass-more-info");assert.deepEqual(event.detail,{entityId:"climate.room"});assert.equal(event.composed,true);
});

test("Demo profiles offer no real HA action targets",async()=> {
 const panel=profileControlPanel([{id:"a",template:"switch",visible:true,demo:true,entity_id:"switch.socket"}]);
 const html=panel.profileControls(panel.data.panels.one);
 assert.match(html,/Demo widgets/);assert.doesNotMatch(html,/data-action="entity-control"/);
 let called=false;panel._hass.callService=async()=>called=true;
 await panel.action("entity-control","switch.socket","one");assert.equal(called,false);
});

test("State updates refresh profile controls only for referenced entities",()=> {
 const panel=profileControlPanel([{id:"a",template:"switch",visible:true,entity_id:"switch.socket"}]);
 const original={state:"off",attributes:{}};
 assert.equal(panel.controlStatesChanged({states:{"switch.socket":original}},{states:{"switch.socket":original,"sensor.other":{state:"10"}}}),false);
 assert.equal(panel.controlStatesChanged({states:{"switch.socket":original}},{states:{"switch.socket":{state:"on"}}}),true);
});


test("Widget name and optional display label render separately for every template",()=> {
 const panel=new Panel();panel.language="en";panel.data={entities:[]};
 for(const template of ["lighting","switch","weather","bc250","actions","clock","temperature_humidity","thermostat"]) {
  const page={template,name:"Editor name",label:"Display caption",entity_id:"",actions:[{entity_id:"",name:""}],umbrella:{enabled:false},disabled_pages:[]};
  const html=panel.pageForm(page);
  assert.match(html,/Widget name/);
  assert.match(html,/data-field="name" required value="Editor name"/);
  assert.match(html,/Display label \(optional\)/);
  assert.match(html,/data-field="label" value="Display caption"/);
  assert.doesNotMatch(html,/data-field="label"[^>]*required/);
 }
 const html=panel.pageForm({template:"switch",name:"Editor name",label:"",entity_id:"switch.room"});
 assert.match(html,/data-field="label" value=""/);
});

test("Editing a display label leaves the widget name unchanged and preserves focus",()=> {
 const panel=new Panel();panel.language="en";const handlers={};
 const input={tagName:"INPUT",type:"text",dataset:{field:"label"},value:"New caption",addEventListener:(event,fn)=>handlers[event]=fn};
 panel.pageId="w";panel.draft={pages:[{id:"w",template:"switch",name:"Editor name",label:"Old caption"}]};
 panel.shadowRoot.querySelectorAll=selector=>selector==="[data-field]" ? [input] : [];
 panel.render=()=>{throw new Error("Text editing must not replace the focused input");};panel.markDirty=()=>{panel.dirty=true;};panel.bind();
 handlers.input();assert.equal(panel.draft.pages[0].name,"Editor name");assert.equal(panel.draft.pages[0].label,"New caption");assert.equal(panel.dirty,true);
});
