import os
from typing import Optional

import torch
from torch import nn
import wandb
from training.train_params import TrainingParams


os.environ["WANDB_MODE"] = "online"


def _train(
    *,
    epoch: int,
    model: nn.Module,
    train_loader: torch.utils.data.DataLoader,
    loss_func: nn.Module,
    optimizer: torch.optim.Optimizer,
):

    model.train()
    running_loss = 0.0
    correct = 0
    total = 0

    for inputs, targets in train_loader:
        inputs, targets = inputs.cuda(), targets.cuda()

        preds = model(inputs)
        loss = loss_func(preds, targets)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        running_loss += loss.item()
        _, predicted = preds.max(1)
        total += targets.size(0)
        correct += predicted.eq(targets).sum().item()

    train_loss = running_loss / len(train_loader)
    train_accuracy = 100.0 * correct / total

    # Log training metrics to wandb
    wandb.log(
        {"Epoch": epoch, "Train Loss": train_loss, "Train Accuracy": train_accuracy}
    )
    print(f"Epoch: {epoch}: Train Loss: {train_loss}, Train Accuracy: {train_accuracy}")
    return train_loss, train_accuracy


def _validate(
    *,
    epoch,
    model: nn.Module,
    val_loader: torch.utils.data.DataLoader,
    loss_func: nn.Module,
):
    model.eval()
    val_loss = 0
    correct, total = 0, 0

    with torch.no_grad():
        for inputs, targets in val_loader:
            inputs, targets = inputs.cuda(), targets.cuda()

            preds = model(inputs)
            loss = loss_func(preds, targets)

            val_loss += loss.item()
            _, predicted = preds.max(1)
            total += targets.size(0)
            correct += predicted.eq(targets).sum().item()

    val_loss = val_loss / len(val_loader)
    val_accuracy = 100.0 * correct / total

    # print(f"Correct: {correct}, Total: {total}")
    # Log validation metrics to wandb
    wandb.log(
        {
            "Epoch": epoch,
            "Validation Loss": val_loss,
            "Validation Accuracy": val_accuracy,
        }
    )
    print(
        f"Epoch: {epoch}: Validation Loss: {val_loss}, Validation Accuracy: {val_accuracy}"
    )
    return val_loss, val_accuracy


def train_model(
    training_params: TrainingParams,
    train_loader: torch.utils.data.DataLoader,
    val_loader: Optional[torch.utils.data.DataLoader] = None,
    project_name: str = "mldl",
) -> float:

    assert isinstance(training_params, TrainingParams)
    assert isinstance(train_loader, torch.utils.data.DataLoader)
    assert isinstance(val_loader, torch.utils.data.DataLoader)

    wandb.init(
        project=project_name,
        name=training_params.training_name,
        config={
            "epochs": training_params.epochs,
            "batch_size": train_loader.batch_size,
            "learning_rate": training_params.learning_rate,
            "architecture": training_params.model.__class__.__name__,
            "optimizer_class": training_params.optimizer_class.__name__,
            "loss_function": training_params.loss_function.__class__.__name__,
            **(training_params.optimizer_params or {}),
        },
    )

    model = training_params.model.cuda()
    loss_func = training_params.loss_function
    optimizer = training_params.optimizer

    best_acc = 0
    num_epochs = training_params.epochs

    for epoch in range(1, num_epochs + 1):
        _, _ = _train(
            epoch=epoch,
            model=model,
            train_loader=train_loader,
            loss_func=loss_func,
            optimizer=optimizer,
        )

        if val_loader:
            _, val_accuracy = _validate(
                epoch=epoch, model=model, val_loader=val_loader, loss_func=loss_func
            )

            # Save the model with the best validation accuracy
            if val_accuracy > best_acc:
                best_acc = val_accuracy
                model_name = f"{training_params.training_name}_best.pth"
                torch.save(model.state_dict(), model_name)
                wandb.save(model_name)

    wandb.finish()
    return best_acc
