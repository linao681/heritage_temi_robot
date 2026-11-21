'use strict';
$('map-select').onchange=()=>switchMap($('map-select').value);
$('add-arrival').onclick=()=>spawnVisitors(Number($('arrival-count').value));
$('retry-success').onclick=()=>clarifySuccess();$('screen-success').onclick=()=>clarifySuccess(true);$('retry-fail').onclick=()=>unclearCommand();
$('staff-apply').onclick=()=>applyStaffAction();$('staff-resume').onclick=()=>resume();
$('staff-safe').onchange=()=>{if(s.handoff)s.handoff.safetyConfirmed=$('staff-safe').checked;};
$('party-size').onchange=()=>{s.manualCount=true;renderUI();};
const metricsCard=$('live-metrics').closest('section');document.querySelector('.interaction').after(metricsCard);
boot();
