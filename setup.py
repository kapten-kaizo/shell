try:
    import os
    a=open("shell.py").read()
    b=os.path.join(os.getenv("PREFIX"),"bin","pyrasite-shell")
    with open(b,"w") as sparator:
        sparator.write(a)
    os.system("chmod 775 %s"%b)
except:
    exit(0)