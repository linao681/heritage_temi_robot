'use strict';
// Device envelope/display use published temi V3 dimensions; motion, sensing and battery remain simulation assumptions.
const MODEL=Object.freeze({
 provenance:'temi V3外观原型；运动与传感为浏览器模型假设，待实机标定；米、秒、弧度、百分比',
 device:Object.freeze({name:'temi V3',width:.35,depth:.45,height:1,displayInches:13.3,displayWidth:.29376,displayHeight:.16524,source:'https://www.robotemi.com/product/temi-sales-contact/',navigationEnvelopeRadius:.34,sdkConnected:false}),
 sensors:Object.freeze({range:Object.freeze({rays:36,fovDegrees:360,hz:10,maxRange:5}),reception:Object.freeze({fovDegrees:108,maxRange:4.8,stableSeconds:1}),seed:20261108}),
 navigationPoseSource:'simulation-ground-truth; estimate is monitoring/recovery only',
 motion:Object.freeze({vMax:.8,wMax:1.2,aMax:.5,alphaMax:2.4,waypointTolerance:.035,trackingReserve:.08,dockTolerance:.055,settleSeconds:.8,headingGain:3,turnThreshold:.32}),
 queue:Object.freeze({gaps:[1.15,1.95,2.75],bodyRadius:.23,robotSeparation:.67,memberSeparation:.46,regroupTimeout:45,lagDistance:.8,lagSpeed:.25,catchupSpeed:.45}),
 crowd:Object.freeze({radius:.27,speed:.55,slowDistance:2.2,stopDistance:1.3,clearDistance:1.7,clearSeconds:.8,detourAfter:3,handoffAfter:12}),
 battery:Object.freeze({initial:86,percentPerMetre:.025,percentPerSecond:.0015,low:20}),
 performance:Object.freeze({reflectionHz:4,reflectionMovingHz:2,telemetryHz:8,trajectorySeconds:.5,maxTrajectory:12000,maxEvents:4000})
});
