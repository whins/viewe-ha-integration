import test from "node:test";
import assert from "node:assert/strict";
import en from "../custom_components/viewe_smart_panel/frontend/locales/en.js";
import uk from "../custom_components/viewe_smart_panel/frontend/locales/uk.js";
import {englishError} from "../custom_components/viewe_smart_panel/frontend/locales/errors.js";

let Panel;
globalThis.HTMLElement=class {
  attachShadow() { this.shadowRoot={innerHTML:"",querySelector:()=>null,querySelectorAll:()=>[]}; }
};
globalThis.customElements={define:(_name,component)=>{Panel=component;}};
globalThis.window={confirm:()=>true};
await import("../custom_components/viewe_smart_panel/frontend/panel.js");

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
