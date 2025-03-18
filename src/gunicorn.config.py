from gevent import monkey; monkey.patch_all()
print("Successfully applied monkey patch")

worker_class = 'gevent'
preload_app = True
