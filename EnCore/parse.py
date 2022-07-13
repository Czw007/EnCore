#!/usr/bin/python3
# -*- coding: UTF-8 -*-
import docker,json,re,os,sys,platform

#parseUser、getGroups、parseOsVersion、isRWable、getStat等是用来获取运行环境信息的函数，可能涉及到容器操作；
#typeChecker、typeRechecker用于配置项类型判断；rulesGenerater、rulesChecker用于生成和验证约束【本工具提到的“约束”、“规则”同义】

#用于获取、解析、保存PHP配置文件，需传入用于找出并打印配置文件的find指令
#返回值：字典类型，配置项为键、配置项的值为值
def parseConf(image,handle,findCMD,save=False,saveDir="conf/"):
	lines=runCommand(handle,findCMD,force=True).split('\n')
	conf=dict()
	for line in lines:
		kv=line.split(";")[0].split("#")[0].split("=")
		if(len(kv)==2):
			k=kv[0].strip()
			v=kv[1].strip()
			if v!="":
				conf[k]=v
	if save:
		os.makedirs(saveDir,exist_ok=True)
		saveContent=""
		for k,v in conf.items():
			saveContent+=k+"="+v+"\n"
		#有些镜像名不能直接作为文件名
		confPath=saveDir+image.replace("/",".").replace(":","_")+".ini"
		with open(confPath,'w') as f:
			f.write(saveContent)
	return conf
#在容器中运行指令
#handle：docker.containers对象，用于操作运行中容器的句柄
#cmd：String类型，等待执行的命令
#返回值：命令执行成功时返回命令的输出，失败时返回None
def runCommand(handle,cmd,force=False):
	t=handle.exec_run(cmd,demux=True)
	if t.exit_code==0 or force:
		return t.output[0].decode('utf-8')
	#print("error",handle.image,cmd,t)
	return None

#从/etc/passwd、/etc/group文件中解析用户、用户组列表
#输入：list类型，是已经分割后的文件内容
#返回：list类型，解析出的用户名/用户组
def parseUser(splitedFileContent):
	user=list()
	for t in splitedFileContent:
		if len(t.split(":"))>1:
			user.append(t.split(":")[0])
	return user
#获取特定用户的所属组（含附属组）
def getGroups(handle,user):
	return runCommand(handle,"id -nG "+user).replace("\n","").split()
#解析并返回操作系统版本等信息
def parseOsVersion(handle):
	osInfo=dict()
	fileContent=runCommand(handle,'cat /etc/os-release').split('\n')
	for t in fileContent:
		t=t.split("=")
		if(len(t)==2):
			osInfo[t[0]]=t[1].strip('"')
	return osInfo
#判断路径是否可被给定的用户读/写，type为"r"时判定读权限，为"w"时判定写权限
def isRWable(handle,path,user,type="w"):
	shells=runCommand(handle,'cat /etc/shells').split('\n')
	#shells=runCommand(handle,'ls /bin/sh /bin/bash /bin/rbash /bin/dash',force=True).split()
	for shell in shells:
		if "#" not in shell and shell!="":
			cmd="su -s '{shell}' {user} -c 'test -{type} {path}'".format(shell=shell,user=user,type=type,path=path)
			t=handle.exec_run(cmd,demux=True)
			if t.exit_code==0:
				#路径存在且给定用户有权限
				return True
			if t.output[1]==None:
				#路径存在且给定用户无权限
				return False
			#文件不存在或其他异常
			return None
	return None
#判断路径是否存在、以及读写权限、所有者、文件类型等信息
def getStat(handle,path,checkAction=None,user=None,type="UserName"):
	res=runCommand(handle,"stat -c '%U %G %a %F' -- "+path)
	if res==None:
		if checkAction=="isExist":
			return False
		return None
	if checkAction=="isExist":
		return True
	elif checkAction=="isFile" and "file" in res:
		return True
	elif checkAction=="isDir" and "directory" in res:
		return True
	elif checkAction=="isOwner":
		if type=="UserName" and user==res.split()[0]:
			return True
		elif type=="GroupName" and user==res.split()[1]:
			return True
	elif checkAction=="isReadable":
		return isRWable(handle,path,user,type="r")
	elif checkAction=="isWriteable":
		return isRWable(handle,path,user,type="w")
	return False
#验证具体的约束是否满足，返回True则判定约束成立，False约束不成立，None为应该忽略该条约束
def rulesChecker(handle,Av,Bv,checkAction,Atype=None,Btype=None):
	if checkAction=="=" and Av==Bv:
		return True
	if checkAction==">" and Av>Bv:
		return True
	if checkAction==">=" and Av>=Bv:
		return True
	if checkAction=="!=" and Av!=Bv:
		return True
	if checkAction=="isInclude" and Av in Bv:
		return True
	if "→" in checkAction:
		a=int(checkAction.split("→")[0])
		b=int(checkAction.split("→")[1])
		if Av!=a:
			return None
		if Bv==b:
			return True
	if checkAction=="isGroup":
		if Bv in getGroups(handle,Av):
			return True
	if checkAction in ["isOwner", "isReadable", "isWriteable","isExist", "isFile", "isDir"]:
		return getStat(handle,Av,checkAction=checkAction,user=Bv,type=Btype)
	return False

#Size类型数值统一化为以KB为单位，便于后续的比较等操作
def sizeFormat(Size):
	size=int(re.match('^[\d]+',Size).group())
	if 'M' in Size:
		size*=1024
	elif 'G' in Size:
		size*=1048576
	elif 'T' in Size:
		size*=1073741824
	return size
#规范化配置项的值，便于操作,当tansBoolean为真时，也转换Boolean类型
def dataTransform(v,type,tansBoolean=False):
	if isinstance(v,str):
		if type=="Size":
			return sizeFormat(v)
		if type=="Number":
			return int(v)
		if type=="Boolean" and tansBoolean:
			if v in ["On","yes"]:
				return True
			else:
				return False
	return v
#关闭所有容器
def closeContainers(client):
	print("Stopping containers…")
	if platform.system()=="Linux":
		os.system('systemctl restart docker')
	for i in client.containers.list():
		i.stop()
	print ("Stop containers successful!")
#读取类型模板文件，生成对应的re对象用于后续的正则匹配操作
def readTypes(templatesFile="templates.json"):
	types=json.loads(open(templatesFile,encoding='utf-8').read())["types"]
	typesData=dict()
	for type,rule in types.items():
		typesData[type]=re.compile(rule)
	return typesData
#初步类型检查，主要进行正则匹配，其中UserName和GroupName类型需要在用户名/用户组列表中
#针对用户名和用户组相同的情况进行了特殊处理，在后续的类型二次检查时减少了用户组误判为用户名的几率
#typesData为用于正则匹配的re对象，users为用户名列表、groups为用户组列表
def typeChecker(typesData,users,groups,v):
	flag=False
	for type in typesData:
		if typesData[type].match(v):
			if type=="UserName":
				if v in users:
					flag=True
				continue
			if type=="GroupName":
				if flag:
					if v in groups:
						return "Name"
					else:
						return "UserName"
				else:
					if v in groups:
						return "GroupName"
				continue
			return type
	return "String"
#配置类型二次检查，当所有镜像中同一个配置项的类型都相同时才将该配置项视为该类型，否则视为String类型
#typeRecorder记录的是初步类型检查后的结果，saveFile是导出的文件名
def typeRechecker(typeRecorder,saveFile="types.json"):
	types=dict()
	for key,values in typeRecorder.items():
		if len(values)>=2:
		#过滤样本中只出现过一次的配置项
			types[key]="String"
			s=set(values)
			if len(s)==1:
				types[key]=values[0]
				if values[0]=="Name":
					types[key]="UserName"
			elif len(s)==2:
				s.discard("Name")
				if len(s)==1:
					types[key]=s.pop()
	with open(saveFile,"w",encoding="utf-8") as f:
		f.write(json.dumps(types))
	return types
#读取表示配置项关联规则的模板，根据其中的类型，生成具体的规则并验证是否成立，其中"max","min","values"为求值型约束，不是用来判定规则是否成立的，处理逻辑略有差异
def rulesGenerater(r,templatesFile="templates.json"):
	print("Generating and validating rules…")
	rules=dict()
	templates=json.loads(open(templatesFile,encoding='utf-8').read())["rules"]
	#A、B是抽象化的配置项类型（如"UserName"、"Size"等），非具体配置项的名称；
	#k1、k2才是具体的配置项名称（如PHP的配置项listen.owner、upload_max_filesize等；
	#item是具体的约束描述（如"=","isInclude"等）
	for A in templates:
		for B,items in templates[A].items():
			for item in items:
				#max、min、values为特殊情况，需要记录具体的值，不必二次判断是否成立
				if item in ["max","min","values"] and A in r["confItems"]:
					for k1 in r["confItems"][A]:
							rules.setdefault(k1,dict())
							rules[k1].setdefault("_self",dict())
							if item in ["max","min"]:
								rules[k1]["_self"][item]=eval(item)(r["confItems"][A][k1].values())
							elif item=="values":
								rules[k1]["_self"][item]=list(set(r["confItems"][A][k1].values()))
				#非max、min、values的情况，需要将规则成立、不成立等情况进行记录，其中True表示成立、False表示不成立、None表示应该忽略(如文件路径不存在时不能确定该FilePath类型的配置项是否和其他配置项有关联)
				else:
					for image in r["confResult"]:
						if A in r["confResult"][image]:
							for k1 in r["confResult"][image][A]:
								if B=="_self" and "is" in item:
									#为了让这种情况也进入下面的循环体，如要这样赋值
									r["confResult"][image]["_self"]={"_self":True}
								if B in r["confResult"][image]:
									for k2 in r["confResult"][image][B]:
										if k1!=k2:
											rules.setdefault(k1,dict())
											rules[k1].setdefault(k2,dict())
											rules[k1][k2].setdefault(item,dict())
											rules[k1][k2][item].setdefault(True,set())
											rules[k1][k2][item].setdefault(False,set())
											rules[k1][k2][item].setdefault(None,set())
											checkResult=rulesChecker(r["containers"][image]["handle"],r["confResult"][image][A][k1],r["confResult"][image][B][k2],checkAction=item,Atype=A,Btype=B)
											rules[k1][k2][item][checkResult].add(image)
	#对上述生成并记录的规则进行二次验证，只有在所有镜像中均满足的规则才被视为成立的约束
	print("reValidating rules…")
	rulesResult=list()
	for k1 in rules:
		for k2 in rules[k1]:
			for item in rules[k1][k2]:
				if isinstance(rules[k1][k2][item],dict):
					if len(rules[k1][k2][item][True])>=2 and len(rules[k1][k2][item][False])==0:
						rulesResult.append({"k1":k1,"k2":k2,"rule":item,"value":True})
				if isinstance(rules[k1][k2][item],int) or isinstance(rules[k1][k2][item],list):
					rulesResult.append({"k1":k1,"k2":k2,"rule":item,"value":rules[k1][k2][item]})
	return rulesResult
#检查新镜像中配置是否正确
def checkConf(config):
	print("Checking configuration…")
	checkReport=""
	client=docker.from_env()
	types=json.loads(open(config["typesFile"],encoding='utf-8').read())
	rules=json.loads(open(config["rulesFile"],encoding='utf-8').read())
	for image in config["checkImages"]:
		imageFullName=image
		if ":" not in image:
			imageFullName=image+":latest"
		print(imageFullName)
		container=client.containers.run(imageFullName,detach=True,auto_remove=True)
		users=parseUser(container.exec_run("cat /etc/passwd").output.decode('utf-8').split('\n'))
		groups=parseUser(container.exec_run("cat /etc/group").output.decode('utf-8').split('\n'))
		conf=parseConf(image,container,config["findCMD"],save=config["saveConf"],saveDir=config["confDir"])
		conf["_id"]=container.id
		conf["_hostname"]=container.attrs['Config']['Hostname']
		conf["_version"]=parseOsVersion(container)["PRETTY_NAME"]
		toDeleteConf=set()
		for k,v in conf.items():
			if k in types:
				type=typeChecker(readTypes(config["templatesFile"]),users,groups,v)
				if type=="Name" and types[k] in ["UserName","GroupName"]:
					continue
				if type!=types[k] and types[k]!="String":
					toDeleteConf.add(k)
					#类型错误
					error="{image} type error: configuration {k} should be {t}, not {type}".format(image=image,k=k,t=types[k],type=type)
					checkReport+=error+"\n"
					print(error,file=sys.stderr)
		for k in toDeleteConf:
			del conf[k]
		#当rule["k2"]="_self"时为了进入循环体且防止访问conf[rule["k2"]]时出错
		conf["_self"]="_self"
		types["_self"]="_self"
		for rule in rules:
			if rule["k1"] in conf:
				if rule["rule"] in ["max","min","values"]:
					v1=dataTransform(conf[rule["k1"]],types[rule["k1"]])
					if rule["rule"] in ["max","min"] and eval(rule["rule"])([v1,rule["value"]])!=rule["value"]:
						#取值范围错误
						error="{image} value error: the {rule} value of {k1} should be {value}. current value is {v1}".format(image=image,k1=rule["k1"],rule=rule["rule"],value=rule["value"],v1=v1)
						checkReport+=error+"\n"
						print(error,file=sys.stderr)
					if rule["rule"]=="values" and v1 not in rule["value"]:
						#取值错误
						error="{image} value error: the value of {k1} should be in {value}. current value is {v1}".format(image=image,k1=rule["k1"],rule=rule["rule"],value=rule["value"],v1=v1)
						checkReport+=error+"\n"
						print(error,file=sys.stderr)
				elif rule["k2"] in conf:
					v1=dataTransform(conf[rule["k1"]],types[rule["k1"]],tansBoolean=True)
					v2=dataTransform(conf[rule["k2"]],types[rule["k2"]],tansBoolean=True)
					checkResult=rulesChecker(container,conf[rule["k1"]],conf[rule["k2"]],rule["rule"],Atype=types[rule["k1"]],Btype=types[rule["k2"]])
					if checkResult==False:
						#不满足配置项之间的约束
						error="{image} rule error: configuration {k2} should {rule} {k1}, but not.".format(image=image,k1=rule["k1"],k2=rule["k2"],rule=rule["rule"])
						checkReport+=error+"\n"
						print(error,file=sys.stderr)
	with open(config["checkResultFile"],'w') as f:
		f.write(checkReport)
	#closeContainers(client)

#初始化工作，用于抓取并保存配置文件、生成并导出类型文件、约束规则文件等
def init(config):
	if not config["generateRules"]:
		return
	images=config["images"]
	client = docker.from_env()
	typesData=readTypes(config["templatesFile"])
	r={"conf":{},"typeRecorder":{},"confItems":{},"confResult":{},"containers":{}}
	#预定义image为镜像名，k、v分别为具体的配置项键和值,type是配置项类型，则变量r结构定义如下：
	#conf[image][k]=v、typeRecorder[k]=list(type)、confItems[type][k][image]=v，confResult[image][type][k]=v
	#containers用来存储容器相关的信息，如容器ID：containers[image]["id"]、容器对象：containers[image]["handle"],系统版本信息：containers[image]["version"]
	#容器中的所有用户：containers[image]["users"]、容器中的所有用户组：containers[image]["groups"]
	for image in images:
		image=image.replace("\n","")
		r["containers"][image]=dict()
		imageFullName=image
		if ":" not in image:
			imageFullName=image+":latest"
		#启动指定的容器并返回用于操作该容器的对象
		container=client.containers.run(imageFullName,detach=True,auto_remove=True)
		r["containers"][image]["handle"]=container
		#r["containers"][image]["id"]=container.id
		#r["containers"][image]["hostname"]=container.attrs['Config']['Hostname']
		#r["containers"][image]["version"]=parseOsVersion(container)["PRETTY_NAME"]
		r["containers"][image]["users"]=parseUser(container.exec_run("cat /etc/passwd").output.decode('utf-8').split('\n'))
		r["containers"][image]["groups"]=parseUser(container.exec_run("cat /etc/group").output.decode('utf-8').split('\n'))
		#抓取、解析、记录镜像内的配置文件
		conf=parseConf(image,container,config["findCMD"],save=config["saveConf"],saveDir=config["confDir"])
		#将部分系统环境信息放到配置信息中
		conf["_id"]=container.id
		conf["_hostname"]=container.attrs['Config']['Hostname']
		conf["_version"]=parseOsVersion(container)["PRETTY_NAME"]
		r["conf"][image]=dict()
		for k,v in conf.items():
			r["conf"][image][k]=v
			r["typeRecorder"].setdefault(k,list())
			r["typeRecorder"][k].append(typeChecker(typesData,r["containers"][image]["users"],r["containers"][image]["groups"],v))
	#types是以字典形式表示的二次判定后的配置项类型，types[配置项]=类型，确定配置项类型后按照最终确定的类型填充r["confItems"]、r["confResult"]用于后续生成规则
	types=typeRechecker(r["typeRecorder"],config["typesFile"])
	print("Export types: ",len(types))
	for image,kv in r["conf"].items():
		for k,v in kv.items():
			if k in types:
				type=types[k]
				#对Size、Number类型格式化成数字，便于后续比较等操作
				v=dataTransform(v,type)
				r["confItems"].setdefault(type, dict())
				r["confItems"][type].setdefault(k, dict())
				r["confItems"][type][k][image]=v
				#此处统一下布尔类型，便于后续规则的判断
				v=dataTransform(v,type,tansBoolean=True)
				r["confResult"].setdefault(image, dict())
				r["confResult"][image].setdefault(type, dict())
				r["confResult"][image][type][k]=v
	#生成验证过的约束规则并导出为json文件
	rules=rulesGenerater(r,templatesFile=config["templatesFile"])
	print("Export rules: ",len(rules))
	with open(config["rulesFile"],"w",encoding="utf-8") as f:
		f.write(json.dumps(rules))
	#closeContainers(client)

#关闭运行中的容器，释放计算资源
closeContainers(docker.from_env())
#加载本工具的配置文件
config=json.loads(open("config.json",encoding='utf-8').read())
#第一次运行需要先执行初始化函数，用于生成并导出配置项的类型、规则文件
init(config["PHP"])
#对新的镜像进行错误检查
checkConf(config["PHP"])
#关闭运行中的容器，释放计算资源
closeContainers(docker.from_env())