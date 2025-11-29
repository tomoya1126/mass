import numpy as np
def softmax(a):
    z=np.max(a)
    sum=np.sum(np.exp(a-z))
    b=np.exp(a-z)/sum
    print(b)
a=np.array([1,2,3])
softmax(a)