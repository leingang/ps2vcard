




function isCrossDomain(objFrame)
{
var isForDomain = false;var domainName="";try
{
 domainName= objFrame.document.domain;} 
catch (exception)
{
 isForDomain = true; }
return isForDomain;}

function isCrossDomainTop() 
{
var objFrame;for (var j=0;j<top.frames.length;j++)
{
 objFrame = top.frames[j]; if (isCrossDomain(objFrame))
 return true; if (objFrame.frames)
 {
 for (var k=0;k<objFrame.frames.length;k++)
 {
 if (isCrossDomain(objFrame.frames[k]))
 return true; }
 }
}
return false;}
