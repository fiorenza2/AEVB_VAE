import torch
import torch.utils.data
from torch import nn, optim
from torch.autograd import Variable
from torch.nn import functional as F
from torchvision import datasets, transforms
from tqdm import tqdm   # Progress bar

from tensorboardX import SummaryWriter

#from torchvision.utils import save_image

class VAE_Net(nn.Module):
    
    # MAIN VAE Class

    def __init__(self, latent_size=20):
        super(VAE_Net, self).__init__()

        # define the encoder and decoder

        self.latent = latent_size

        self.ei = nn.Linear(28 * 28 * 1, 500)
        self.em = nn.Linear(500, self.latent)
        self.ev = nn.Linear(500, self.latent)

        self.di = nn.Linear(self.latent, 500)
        self.do = nn.Linear(500, 28 * 28 * 1)

    def encode(self, x):

        # encoder part

        o = F.sigmoid(self.ei(x))
        mu = self.em(o)
        logvar = self.ev(o)
        return mu, logvar

    def decode(self, x):

        # decoder part    

        o = F.sigmoid(self.di(x))
        im = F.sigmoid(self.do(o))
        return im

    def sample(self):

        # get a N(0,1) sample in a torch/cuda tensor        

        return Variable(torch.randn(self.latent).cuda(), requires_grad = False)

    def repar(self, mu, logvar):

        # the infamous reparamaterization trick (aka 4 lines of code)

        samp = self.sample()
        samp = F.mul((0.5*logvar).exp(),samp)
        samp = samp + mu
        return samp

    def forward(self, x):

        # forward pass (take your image, get its params, reparamaterize the N(0,1) with them, decode and output)

        mu, logvar = self.encode(x)
        f = self.decode(self.repar(mu,logvar))
        return f, mu, logvar



def elbo_loss(mu, logvar, x, x_pr):

    # ELBO loss; NB: the L2 Part is not necessarily correct
    # BCE actually seems to work better, which tries to minimise informtion loss (in bits) between the original and reconstruction
    # TODO: make the reconstruction error resemble the papers

    size = mu.size()
    KL_part = 0.5*((logvar.exp().sum() + mu.dot(mu) - size[0]*size[1] - logvar.sum()))
    Recon_part = F.binary_cross_entropy(x_pr, x, size_average=False)
    #Recon_part = F.mse_loss(x_pr, x, size_average=False)
    #print('L2 loss: %.6f' % L2_part)
    #print('kL loss: %.6f' % KL_part)
    return Recon_part + KL_part



def get_data_loaders(b_size):

    # downloads the MNIST data, outputs these PyTorch wrapped data loaders
    # TODO: MAKE THIS DATASET AGNOSTIC

    kwargs = {'num_workers': 1, 'pin_memory': True}
    train_loader = torch.utils.data.DataLoader(
        datasets.MNIST('../data', train=True, download=True,
                       transform=transforms.ToTensor()),
                        batch_size=b_size, shuffle=True, **kwargs)
    test_loader = torch.utils.data.DataLoader(
        datasets.MNIST('../data', train=False, download=True,
                       transform=transforms.ToTensor()),
                        batch_size=b_size, shuffle=True, **kwargs)
    return train_loader, test_loader



def train(model, optimizer, train_loader, loss_func, epochs = 1, show_prog = 100, summary = None):

    # stolen from a generic pytorch training implementation
    # TODO: Train on different data
    
    if summary:
        writer = SummaryWriter(summary)

    b_size = float(train_loader.batch_size)
    
    model.train()
    for i in tqdm(range(epochs)):
        for batch_idx, (data, _ ) in enumerate(train_loader):

            n_iter = (i*len(train_loader))+batch_idx
            
            data = Variable(data, requires_grad = False).view(-1,784)  # NEED TO FLATTEN THE IMAGE FILE
            data = data.cuda()  # Make it GPU friendly
            optimizer.zero_grad()   # reset the optimzer so we don't have grad data from the previous batch
            output, mu, var = model(data)   # forward pass
            loss = loss_func(mu, var, data, output) # get the loss
            if summary:
                # write the negative log likelihood ELBO per data point to tensorboard
                writer.add_scalar('ave loss/datapoint', -loss.data[0]/b_size, n_iter)
            loss.backward() # back prop the loss
            optimizer.step()    # increment the optimizer based on the loss (a.k.a update params?)
            #print('Batch Training Loss is: %.6f' % loss[0])
            if batch_idx % show_prog == 0:
                print('Train Epoch: {} [{}/{} ({:.0f}%)]\tLoss: {:.6f}'.format(
                    i, batch_idx * len(data), len(train_loader.dataset),
                    100. * batch_idx / len(train_loader), loss.data[0]))
                if summary:
                    writer.add_image('real_image', data[1].view(-1,28,28), n_iter)
                    a,_,_ = model(data[1].cuda())
                    writer.add_image('reconstruction', a.view(-1,28,28), n_iter)
                    b = model.decode(model.sample())
                    writer.add_image('from_noise', b.view(-1,28,28), n_iter)

def init_weights(m):
    print("Messing with weights")
    print(m)
    if type(m) == nn.Linear:
        m.weight.data.normal_(0,0.01)
