'use strict';
// Screen-based observation tasks, not demonstrations of hands-on craft practice.
const EXPLORATION_TASKS=[
 {title:'认识非遗',question:'理解非遗，哪种说法更完整？',options:['展品背后的知识、技能和实践','只要保存成品就能传承所有技艺'],correct:0,explanation:'物品是理解的线索，非遗还包括被认同并持续传承的实践、知识与技能。',source:'U1'},
 {title:'认识工具和工序',question:'比较两种工艺时，应先做什么？',options:['外形相似，就判断工序相同','观察材料、工具与操作，再查核资料'],correct:1,explanation:'同样外形可能来自不同方法。观察是提出问题的起点，不能替代具体工艺资料。',source:'U3'},
 {title:'观察作品细节',question:'看到作品纹样后，怎样形成可靠结论？',options:['记录形状与细节，将作者年代交给档案核实','仅凭纹样相似，直接确定年代与作者'],correct:0,explanation:'直接观察与历史判断应分开；作者、年代和流传需要可靠档案支持。',source:'CASE'},
 {title:'理解传承经历',question:'从三位传承人的经历，可以得到什么认识？',options:['所有手艺都遵循完全一样的学习路径','学习路径各有不同，需尊重个人与地域语境'],correct:1,explanation:'家庭学习、专业学习与修缮实践呈现不同路径，不能用单个人物概括所有传承。',source:'HFL',sources:['HFL','YJP','GFL']},
 {title:'完成知识挑战',question:'参观后，怎样继续学习更合适？',options:['先理解材料和工具，在指导下体验','答对屏幕题，就已经掌握真实制作技艺'],correct:0,explanation:'屏幕答题仅是观察回顾。真实制作需要材料、工具、练习与工作人员指导。',source:'CASE'},
];
function resetExploration(){s.exploration={completed:[],attempts:[],openZone:null};$('quiz').hidden=true;}
function renderExploration(){
 const e=s.exploration;if(!e)return;
 $('exploration-progress').textContent='五区探索 '+e.completed.length+'/5 · '+EXPLORATION_TASKS.map((t,i)=>(e.completed.includes(i)?'✓ ':'○ ')+(i+1)).join('  ');
 $('interact').textContent=s.index<5?'本区探索 · '+(s.index+1):'五区探索';
}
function openExploration(){
 if(s.paused||s.faults.length||s.index>=5||!['speaking','question'].includes(s.phase)||s.questionReturn==='moving')return false;
 const task=EXPLORATION_TASKS[s.index];s.exploration.openZone=s.index;s.elapsed=0;
 show('07 / 五区探索 · '+(s.index+1)+'/5',task.title,task.question+'\n答题是屏幕观察回顾；真实动手体验由工作人员指导。');renderSources(task.sources||[task.source]);
 $('quiz-cross').textContent=task.options[0];$('quiz-glue').textContent=task.options[1];$('quiz-feedback').textContent='请选择一项。';$('quiz').hidden=false;renderExploration();return true;
}
function answerExploration(choice){
 const e=s.exploration;if(!e||$('quiz').hidden||e.openZone!==s.index||s.paused||s.faults.length||!['speaking','question'].includes(s.phase))return false;
 const task=EXPLORATION_TASKS[s.index],correct=choice===task.correct;
 e.attempts.push({t:sim.time,zoneId:s.index+1,task:task.title,question:task.question,choice,selected:task.options[choice],correct,explanation:task.explanation,sourceId:task.source,sourceIds:task.sources||[task.source]});
 if(correct&&!e.completed.includes(s.index))e.completed.push(s.index);
 $('quiz-feedback').textContent=(correct?'回答正确。':'再想一想。')+task.explanation;renderSources(task.sources||[task.source]);
 if(correct){s.interactionDone=e.completed.length===5;s.elapsed=0;log('五区探索 → '+(s.index+1)+'区完成 / '+e.completed.length+'/5');}
 renderExploration();return correct;
}
$('interact').onclick=openExploration;
$('quiz-cross').onclick=()=>answerExploration(0);$('quiz-glue').onclick=()=>answerExploration(1);
