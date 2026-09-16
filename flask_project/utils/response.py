from flask import jsonify
def success(data=None,msg="success",code=200):
    """响应封装"""
    response={
        'data':data,
        'msg':msg,
        'code':code
    }
    return jsonify(response),code

def error(data=None,msg="error",code=400):
    """响应封装"""
    response={
        'data':data,
        'msg':msg,
        'code':code
    }
    return jsonify(response),code

