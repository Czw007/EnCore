#### Linux 下载安装Augeas

###### Step 1

Run update command to update package repositories and get latest package information.

```
sudo apt-get update -y
```

###### Step 2

Run the install command with -y flag to quickly install the packages and dependencies.

```
sudo apt-get install -y augeas-tools
```

#### Augeas使用

##### github源码链接：

[https://github.com/hercules-team/augeas](https://github.com/hercules-team/augeas)

augtool只能解析能识别的配置文件：

例如augtool只能识别mysql中的

![image-20211019182414211](/Users/changzw/Library/Application Support/typora-user-images/image-20211019182414211.png)

![image-20211019182245117](/Users/changzw/Library/Application Support/typora-user-images/image-20211019182245117.png)

但真正配置文件是

```
/etc/mysql/mysql.conf.d/mysqld.cnf
```

因此需要将该文件转换成augtool能够识别的文件

```
augtool --noautoload --transform "MySQL.lns incl /etc/mysql/mysql.conf.d/mysqld.cnf"
```

![image-20211019182753862](/Users/changzw/Library/Application Support/typora-user-images/image-20211019182753862.png)

解析成功



#### 解析mongoDB

配置文件位置为

```
/etc/mongodb.conf
```

解析命令

```
augtool print /files/etc/mongodb.conf
```

![image-20211019191521477](/Users/changzw/Library/Application Support/typora-user-images/image-20211019191521477.png)

#### 解析Squid

配置文件位置为

```
/etc/squid/squid.conf
```

解析命令

```
augtool print /files/etc/squid/squid.conf
```

无输出，需要转换

转换命令：

![image-20211019192229102](/Users/changzw/Library/Application Support/typora-user-images/image-20211019192229102.png)

好像Squid没有lens，可以使用Redis.lns替代一下

#### 解析nginx

![image-20211019191102912](/Users/changzw/Library/Application Support/typora-user-images/image-20211019191102912.png)



#### 注意：

augeas只能解析配置文件，但不会直接转换成键值对，如何转换需要自己制定规则

例如如何将解析后的Nginx配置文件转换成键值对，见论文：

《ConfEx: A Framework for Automating Text-based Software Configuration Analysis in the Cloud》