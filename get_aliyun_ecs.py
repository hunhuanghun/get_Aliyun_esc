#!/usr/bn/env python
# -*- coding: utf8 -*-
# Author: fiona.li
# Function : 获取aliyun ecs实例的监控数据

from aliyunsdkcore.client import AcsClient
from aliyunsdkecs.request.v20140526 import DescribeInstancesRequest
from aliyunsdkcms.request.v20170301 import QueryMetricListRequest
import time
import datetime
import json

# 创建 AcsClient 实例
client = AcsClient(
    '<access-key-id>', 
    '<access-key-secret>',    
    '<region-id>',
);

# 获取前一天00:00:00距离1970年1月1日0点的毫秒数
def get_lastday_time():
    date_time = {}
    cur_date = datetime.date.today()
    oneday = datetime.timedelta(days=1)
    yesterday = str(cur_date - oneday)
    lastday = str(cur_date - oneday - oneday)
    start = yesterday+" "+"00:00:00"
    end = yesterday+" "+"23:59:59"
    date_time['time_start'] = int(time.mktime(time.strptime(start, "%Y-%m-%d %H:%M:%S"))) * 1000
    date_time['time_end'] = int(time.mktime(time.strptime(end, "%Y-%m-%d %H:%M:%S"))) * 1000
    return date_time

# 计算实例总共有多少页
def get_page_number(total_count,pagesize):
    page_number = 1
    if pagesize < total_count:
        page_number = total_count / pagesize
        remainder = total_count % pagesize
        if remainder > 0 :
            page_number = page_number + 1
    return page_number


def Conversion_format(instances):
    datas = []
    for instance in instances :
        data = {}
        data['InstanceId'] = instance['InstanceId']
        data['InstanceName'] = instance['InstanceName']
        data['Cpu'] = instance['Cpu']
        data['Memory'] = int(instance['Memory']) / 1024
        data['OSType'] = instance['OSType']
        datas.append(data)
    return datas

# 根据阿里云的查询实例数据的SDK去获取所有实例ID及其基本信息
def get_aliyun_instanceId():
    request = DescribeInstancesRequest.DescribeInstancesRequest()
    request.set_accept_format("JSON")
    total_count = json.loads(client.do_action_with_exception(request)).get("TotalCount")
    pagesize = 10
    page_number = get_page_number(total_count,pagesize)
    datas = []
    for num in range(1,page_number+1) : 
        data = []
        req = DescribeInstancesRequest.DescribeInstancesRequest()
        req.set_accept_format("JSON")
        request.set_PageSize(pagesize)
        req.set_PageNumber(num)
        instances = json.loads(client.do_action_with_exception(req)).get("Instances").get("Instance")
        data = Conversion_format(instances)
        datas.extend(data)
    return datas

# 设置统一的查询监控项的函数参数
def query_metric_request(m,date_time,Id):
    request = QueryMetricListRequest.QueryMetricListRequest()
    request.set_accept_format('json')
    request.set_Project('acs_ecs_dashboard')
    request.set_Metric(m)
    request.set_StartTime(date_time["time_start"])
    request.set_EndTime(date_time["time_end"])
#    request.set_Dimensions([{'instanceId':Id}])
    request.set_Dimensions("{'instanceId':'%s'}" % Id)
    request.set_Period('86400')
    # 发起 API 请求并打印返回
    response = json.loads(client.do_action_with_exception(request))
    return response

# 获取各监控项的数据
def get_monitoring_data(instances,date_time,metric):
    for count,instance in enumerate(instances):
        for t in metric:
            instances[count][t["metric_type"]] = {}
            for m in t["metric"]:
                instances[count][t["metric_type"]][m]={}
                response = query_metric_request(m,date_time,instance["InstanceId"])
                status = str(response.get("Success"))
                code = int(response.get("Code"))
#                if len(response.get('Datapoints')) == 0:
#                    print instance['InstanceName'] 
                if code == 200 :
                    datapoints = response.get('Datapoints')
                    if len(datapoints) == 0 :
                        instances[count][t["metric_type"]][m]["Maximum"] = "None"
                        instances[count][t["metric_type"]][m]["Average"] = "None"
                    elif len(datapoints) == 1 and m != "diskusage_total" and m != "diskusage_utilization":
                        instances[count][t["metric_type"]][m]["Maximum"] = datapoints[0]['Maximum']
                        instances[count][t["metric_type"]][m]["Average"] = datapoints[0]['Average']
                    elif len(datapoints) >= 1 and m == "diskusage_total" :
                        for d in datapoints:
                            disk_name = d.get('diskname')
                            disk_space = round(float(d.get('Average'))/1024/1024/1024)
#                           print instance['InstanceName'],disk_name,disk_space
                            instances[count][t["metric_type"]][m][disk_name] = str(disk_space)+"G"
                    elif len(datapoints) >= 1 and m == "diskusage_utilization" :
                        for d in datapoints:
                            disk_name = d.get('diskname')
                        #    print instance['InstanceName'],disk_name,d.get('Maximum') 
                            instances[count][t["metric_type"]][m][disk_name] = d.get('Maximum') 
    return instances       
                        
# 将要输出的数据格式化
def format_output(instances):
    for instance in instances:
        HostName = instance.get('InstanceName')
        Cpu_nums = instance.get('Cpu')
        Cpu_max_utilization = instance.get('Cpu_usage').get('cpu_total').get('Maximum')
        Cpu_max_load = instance.get('Cpu_usage').get('load_5m').get('Maximum')
        Memory_size = instance.get('Memory') 
        Memory_max_utilization = instance.get('Mem_usage').get('memory_usedutilization').get('Maximum')
        if instance.get('OSType') == 'linux':
            Disk_root_size = instance.get('Disk_usage').get('diskusage_total').get(u'/')
            Disk_data_size = instance.get('Disk_usage').get('diskusage_total').get(u'/data')
            Disk_root_utilization = instance.get('Disk_usage').get('diskusage_utilization').get(u'/')
            Disk_data_utilization = instance.get('Disk_usage').get('diskusage_utilization').get(u'/data')
        else:
            Disk_root_size = instance.get('Disk_usage').get('diskusage_total').get(u'C:\\')
            Disk_data_size = instance.get('Disk_usage').get('diskusage_total').get(u'D:\\')
            Disk_root_utilization = instance.get('Disk_usage').get('diskusage_utilization').get(u'C:\\')
            Disk_data_utilization = instance.get('Disk_usage').get('diskusage_utilization').get(u'D:\\')
        Networkin_rate = instance.get('Network_rate').get('networkin_rate').get('Maximum')
        if isinstance(Networkin_rate,(int,float)):
           Networkin_rate = round(int(Networkin_rate)/8.0/1024.0)
           Networkin_rate = str(Networkin_rate)+"KB/s"
        Networkout_rate = instance.get('Network_rate').get('networkout_rate').get('Maximum')
        if isinstance(Networkout_rate,(int,float)):
           Networkout_rate = round(int(Networkout_rate)/8.0/1024.0)
           Networkout_rate = str(Networkout_rate) + "KB/s"
        print HostName+"\t"+str(Cpu_nums)+"\t"+str(Cpu_max_utilization)+"\t"+str(Cpu_max_load)+"\t"+str(Memory_size)+"\t"+str(Memory_max_utilization)+"\t"+str(Disk_root_size)+"\t"+str(Disk_root_utilization)+"\t"+str(Disk_data_size)+"\t"+str(Disk_data_utilization)+"\t"+str(Networkin_rate)+"\t"+str(Networkout_rate)
                
def main():
    metric = [{"metric_type":"Cpu_usage","metric":["cpu_total","load_5m","cpu_wait"]},
              {"metric_type":"Mem_usage","metric":["memory_usedutilization"]},
              {"metric_type":"Disk_usage","metric":["diskusage_utilization","diskusage_total"]},
              {"metric_type":"Network_rate","metric":["networkin_rate","networkout_rate"]}
             ]
    datas = get_aliyun_instanceId()
    date_time = get_lastday_time()
    aliyun_instances = get_monitoring_data(datas,date_time,metric)
    print "主机名	CPU核数	CPU最高利用率	CPU最高负载	内存大小	内存最高使用率	根分区大小	根分区最高使用率	数据分区大小	数据分区最高使用率	上行带宽	下行带宽"
    format_output(aliyun_instances)


if __name__ == "__main__":
    main()
